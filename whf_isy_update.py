#!/usr/bin/env python
#

__author__ = 'Daniel Rich <drich@employees.org>'
__copyright__ = "Copyright (C) 2016 Daniel Rich"
__license__ = "BSD"
__version__ = "0.1"

import os
import sys
import getopt
import logging
from logging import NullHandler
import urllib2
import ssl
import BaseHTTPServer           # For error responses
import xml.etree.ElementTree as ET
import re

def setup_logging(level=logging.NOTSET):
    if level > logging.NOTSET:
        logging.basicConfig(level=level)
        logging.logThreads = True
        if hasattr(logging,'captureWarnings'):
            logging.captureWarnings(True)
        handler.setLevel(level)

        formatr = logging.Formatter("%(relativeCreated)-4d L%(lineno)-4d:%(funcName)-18.18s %(levelname)-7.7s %(message)s")
        handler.setFormatter(formatr)
    else:
        handler = NullHandler()

    log = logging.getLogger('vault')
    log.addHandler(handler)
    log.setLevel(level)
    return log

# Fetch the specified URL, managing cookies
def fetchURL(url='', method='', data=None, headers={}, user='', passwd=''):
    """
    Retrieves the specified URL

    Args:
        url (string): URL resource with any parameters
        method (string): method to use: GET, PUT, POST
        data (string): data to send on a POST or PUT request
        headers (dict): dictionary of headers to send with the request
        user (string): user for authenticated URLs
        passwd (string): passwd for authenticated URLs
    Returns:
        The content of the requested page
    """
    if user:
        log.debug("fetchURL(%s, %s, %s, %s, %s)" % (url, method, str(data), user, passwd))
    else:
        log.debug("fetchURL(%s, %s, %s)" % (url, method, str(data)))
    req = urllib2.Request(url, data, headers)
    # This is ugly -- allow self-signed certs by creating a context
#    if 'https' in url:
#        ctx = ssl.create_default_context()
#        ctx.check_hostname = False
#        ctx.verify_mode = ssl.CERT_NONE
    # Configure authentication if needed
    if user:
        authinfo = urllib2.HTTPPasswordMgrWithDefaultRealm()
        authinfo.add_password(None, url, user, passwd)
        authmgr = urllib2.HTTPBasicAuthHandler(authinfo)
        opener = urllib2.build_opener(authmgr)
        urllib2.install_opener(opener)
    try:
        if 'https' in url:
            #resp = urllib2.urlopen(req, context=ctx)
            resp = urllib2.urlopen(req)
        else:
            resp = urllib2.urlopen(req)
    except urllib2.HTTPError as e:
        if e.code == 404:
            return(e.code)      # Return "404" for not found, let the caller deal with it
            log.info("Request failed to %s: %s" % (url, BaseHTTPServer.BaseHTTPRequestHandler.responses[e.code][0]))
        # Attempt to get content if any
        log.debug("URL returned %d: %s" % (e.code, e.args))
        raise

    except urllib2.URLError as e:
        print "Vault request failed: %s" % e.reason
        raise Exception(e.reason)

    content = resp.read()
    log.debug(content)
    resp.close()

    return(content)


def getISYVars(host='', user='', passwd='', ssl=True):
    """
    Query ISY for variable names (both boolean and integer)
    and return a dict of vars
    Args:
        host (string): ISY hostname
        user (string): ISY user
        passwd (string): ISY password
        ssl (boolean): Use SSL if true
    """

    vardict = {}
    url = "http://%s/rest/vars/definitions/" % host
    if ssl:
        url = "https://%s/rest/vars/definitions/" % host

    for vartype in [1,2]:
        vardict[vartype] = {}
        try:
            vardata = fetchURL("%s%d" % (url, vartype), user=user, passwd=passwd)
        except Exception as e:
            print "ISY query failed: %s" % e
            sys.exit(1)
            
        # Parse the XML
        root = ET.fromstring(vardata)
        for e in root:
            vardict[vartype][e.attrib['id']] = e.attrib['name']

    return(vardict)
            

def getWHFData(host=''):
    """
    Query whole house fan for data
    This is something of a pain since it doesn't return valid XML
    Args:
        host (string): Whole house fan hostname
    Returns:
        The content of the requested page
    """
    try:
        whfdata = fetchURL("http://%s/fanspd.cgi" % host)
    except Exception as e:
        print "Airscape query failed: %s" % e
        sys.exit(1)

    whfDict = {}
    # Attempt to parse the output by finding tagged values
    pattern = re.compile('<([^>]+)>([^<]+)</([^>]+)>',flags=re.MULTILINE)
    patternSub = re.compile('^.*?<([^>]+)>([^<]+)</([^>]+)>',flags=re.MULTILINE)
    match = pattern.search(whfdata)
    while match != None:
        whfDict[match.group(1)] = match.group(2)
        whfdata = patternSub.sub('',whfdata,count=1)
        match = pattern.search(whfdata)
    
    return(whfDict)

def setISYVars(host='', user='', passwd='', ssl=True, isyVars={}, fanData={}):
    """
    Update ISY vars with data from fan for all defined variables
    ISY variables must be prefixed with whf_ and match the variable
    names returned by the Airscape to be udpated
    Args:
        host (string): ISY hostname
        user (string): ISY user
        passwd (string): ISY password
        ssl (boolean): Use SSL if true
        isyVars (dict): Dictionary from getISYVars of all ISY vars
        fanData (dict): Dictionary of fan data, key: var name, value: value
    """

    baseURL = "http://%s/rest/vars/set" % host
    if ssl:
        baseURL = "https://%s/rest/vars/set" % host

    for vartype in [1,2]:
        for varid,varname in isyVars[vartype].iteritems():
            fanvar = re.sub('whf_','',varname)
            if fanvar in fanData:
                log.debug('Setting %s=%s' % (varname, fanData[fanvar]))
                try:
                    vardata = fetchURL("%s/%d/%s/%s" % (baseURL, vartype, varid, fanData[fanvar]), user=user, passwd=passwd)
                except Exception as e:
                    print "ISY query failed: %s" % e
                    sys.exit(1)
            

def usage(message=''):
    print message
    print """usage: """ + sys.argv[0] + """ [-f|--fanhost fanhost] [-h|--isyhost isyhost] [--ssl=yes|no] [-u|--user username[:password]] [-p|--password password] [-D|--debug]n
        fanhost  - host name of the Airscap device (default: whf)
        isyhost  - host name of the ISY device (default: isy)
        username - username with admin rights to the ISy (default: admin)
        password - password for the above user (default: admin)
        debug    - enable debugging
"""
    sys.exit(1)

    
# defaults
# Parse command line
try:
    opts,args = getopt.getopt(sys.argv[1:], 'h:u:p:vl:S:D', ['host=', 'user=', 'password=', 'ssl=', 'verbose', 'debug', 'daemon', 'pidfile=', 'logfile=', 'syslog='])
except getopt.GetoptError, err:
    print str(err)
    usage()


    
# Defaults
fanHost = 'whf'
isyHost = 'isy'
isyUser = 'admin'
isyPass = 'admin'
isySSL = True
debug = False
    
# Parse command line
try:
    opts,args = getopt.getopt(sys.argv[1:], 'f:h:u:p:D', ['fanhost=', 'isyhost=', 'user=', 'password=', 'ssl=', 'debug'])
except getopt.GetoptError, err:
    print str(err)
    usage()

for o, a in opts:
    if o in ('-f', '--fanhost'):
        fanHost = a
    elif o in ('-h', '--isyhost'):
        isyHost = a
    elif o in ('-u', '--user'):
        isyUser = a
        if ':' in isyUser:
            (isyUser,isyPass) = isyUser.split(':')
    elif o in ('-p', '--password'):
        isyPass = a
    elif o in ('--ssl'):
        if a and a == 'no':
            isySSL = False
        else:
            isySSL = True
    elif o in ('-D', '--debug'):
        debug = True
        logging.basicConfig(level=logging.DEBUG)

# Setup logging (mostly for debugging)
log = setup_logging()
isyVars = getISYVars(isyHost, isyUser, isyPass, isySSL)
fanData = getWHFData(fanHost)
setISYVars(isyHost, isyUser, isyPass, isySSL, isyVars, fanData)
