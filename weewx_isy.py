# Copyright 2016 Daniel Rich <drich@employees.org>

"""
This is a weewx extension that uploads data to a Universal Devices ISY
Insteon controller.
It will update any variables named weewx_xxx, where xxx is the name of
a weewx value. E.g. weewx_outTemp

https://www.universal-devices.com/residential/isy994i-series/

Minimal Configuration:

[StdRESTful]
    [[ISY]]
        server_url = ISY_URL
	user = ISY_USERNAME
	password = ISY_PASSWORD

The ISY API, including documenation on setting and fetching variables, is 
available on the ISY wiki:

http://wiki.universal-devices.com/index.php?title=ISY_Developers:API:REST_Interface
"""

import Queue
import re
import sys
import syslog
import time
import urllib
import urllib2
import base64
import xml.etree.ElementTree as ET

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool, accumulateLeaves

VERSION = "0.1"

if weewx.__version__ < "3":
    raise weewx.UnsupportedFeature("weewx 3 is required, found %s" %
                                   weewx.__version__)

def logmsg(level, msg):
    syslog.syslog(level, 'restx: ISYUploader: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def _get_rain(dbm, start_ts, end_ts):
    val = dbm.getSql("SELECT SUM(rain) FROM %s "
                     "WHERE dateTime>? AND dateTime<=?" %
                     dbm.table_name, (start_ts, end_ts))
    return val[0] if val is not None else None

class ISYUploader(weewx.restx.StdRESTbase):
    def __init__(self, engine, config_dict):
        """This service recognizes standard restful options plus the following:

        server_url: ISY device URL
	Default is "http://isy/"

        user: ISY device username
	Default is "admin"

        password: ISY device password
	Default is "admin"

        """
        super(ISYUploader, self).__init__(engine, config_dict)
        loginf("service version is %s" % VERSION)
        try:
            site_dict = config_dict['StdRESTful']['ISY']
            site_dict = accumulateLeaves(site_dict, max_level=1)
            #site_dict['server_url']
            #site_dict['user']
            #site_dict['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('server_url', 'http://isy/')
        site_dict.setdefault('user', 'admin')
        site_dict.setdefault('password', 'admin')
	site_dict['ISYvars'] = {}
        site_dict['manager_dict'] = weewx.manager.get_manager_dict(
            config_dict['DataBindings'], config_dict['Databases'], 'wx_binding')

        self.archive_queue = Queue.Queue()
        self.archive_thread = ISYUploaderThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded for server_url=%s user=%s" % 
               (site_dict['server_url'], site_dict['user']))

	# Query ISY for existing integer variables
	url = "%s/%s" % (site_dict['server_url'], "rest/vars/definitions/1")
	req = urllib2.Request(url)
	req.get_method = lambda: 'GET'
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
	base64string = base64.encodestring('%s:%s' % (site_dict['user'], site_dict['password'])).replace('\n', '')
	req.add_header("Authorization", "Basic %s" % base64string)   
        resp = urllib2.urlopen(req)
	vardata = resp.read()
	# Parse the XML
        root = ET.fromstring(vardata)
        for e in root:
	    if 'weewx' in e.attrib['name']:
		site_dict['ISYvars'][e.attrib['name']] = e.attrib['id']

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class ISYUploaderThread(weewx.restx.RESTThread):

    def __init__(self, queue,
		 server_url, user, password, ISYvars,
                 manager_dict,
                 post_interval=None, max_backlog=sys.maxint, stale=None,
                 log_success=True, log_failure=True,
                 timeout=60, max_tries=3, retry_wait=5):
        super(ISYUploaderThread, self).__init__(queue,
                                               protocol_name='ISY',
                                               manager_dict=manager_dict,
                                               post_interval=post_interval,
                                               max_backlog=max_backlog,
                                               stale=stale,
                                               log_success=log_success,
                                               log_failure=log_failure,
                                               max_tries=max_tries,
                                               timeout=timeout,
                                               retry_wait=retry_wait)
	self.server_url = server_url
	self.user = user
	self.password = password
	self.ISYvars = ISYvars

    def process_record(self, record, dbm):
        r = self.get_record(record, dbm)
	# Loop through observation values. If ISY varibale weewx_<datapoint>
	# exists, update it
	for k in r:
	    if "weewx_%s" % k in self.ISYvars:
		url = "%s/rest/vars/set/1/%s/%d" % (self.server_url, self.ISYvars["weewx_%s" % k], int(r[k]))
        	req = urllib2.Request(url)
		req.get_method = lambda: 'GET'
        	req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
		base64string = base64.encodestring('%s:%s' % (self.user, self.password)).replace('\n', '')
		req.add_header("Authorization", "Basic %s" % base64string)   
        	self.post_with_retries(req)
