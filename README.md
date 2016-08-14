# ISY-utils
Various utilities for working with the Universal Devices ISY994i/ISY99i

## weewx_isy.py

Module to upload weewx metrics to an [isy994i] controller (while not tested this should also work on an isy99i).

This module should be installed into the user directory of your [weewx] installation (e.g. /usr/share/weewx/user/isy.py). It will update any integer variables named *weewx_xxx* every weewx archive cycle. As an example, *weewx_outTemp*, *weewx_inTemp*, and *weewx_outHumidity*.

The configuration is done through the *weewx.conf* file, in the *[StdRESTful]*
 block. It supports the standard weewx REST configuartion values as well as the ISY server url, username, and password needed for authentication. These default to http://isy/, admin, and admin respectively if not specified.

    [StdRESTful]
       [[ISY]]
          server_url = http://isy/
          user = admin
          password = *vosys

You will also need to add the *user.isy.ISYUploader* module to the *restful_serivces* configuartion:

    restful_services = weewx.restx.StdStationRegistry, weewx.restx.StdWunderground, weewx.restx.StdPWSweather, weewx.restx.StdCWOP, user.isy.ISYUploader


## whf_isy_update.py

This utility queries an [Airscape] Whole House Fan to update variables as long as the fan supports the [Airscape Gen2 API]. The varables must be named whf_xxx, where xxx can be any of the values returned via. the Airscape REST api:
* fanspd
* doorinprocess
* timeremaining
* macaddr
* ipaddr
* model
* softver
* interlock1
* interlock2
* cfm
* power
* house_temp
* DNS1
* attic_temp
* oa_temp
* server_response
* DIPS
* switch2

E.g. variables could be named whf_fanspd, whf_power, etc.

```
usage: whf_isy_update [-f|--fanhost fanhost] [-h|--isyhost isyhost] [--ssl=yes|no] [-u|--user username[:password]] [-p|--password password] [-D|--debug]n
        fanhost  - host name of the Airscap device (default: whf)
        isyhost  - host name of the ISY device (default: isy)
        username - username with admin rights to the ISy (default: admin)
        password - password for the above user (default: admin)
        debug    - enable debugging
```

This could be run via. cron, as an example:
```
*/5 * * * * /usr/local/bin/whf_isy_update --user 'admin:admin' --ssl=no
```

## ISY Example Usage

When used with the [isy994i] and [network resources], this code could be used to turn off the whole house fan if it is warmer outside than it is inside:

```
If
      $whf_fanspeed >= 1
  And $weewx_outTemp >= $weewx_inTemp
Then
      Resource 'Airscape_Off'
```

[isy994i]: https://www.universal-devices.com/residential/
[network resources]: http://wiki.universal-devices.com/index.php?title=ISY-994i_Series_INSTEON:Networking:Network_Resources
[weewx]: http://www.weewx.com
[Airscape]: http:///airscapefans.com/
[Airscape Gen2 API]: http://blog.airscapefans.com/archives/gen-2-controls-api
