launchpad-reporting
===================

Convenient web-based frontend for Launchpad. Displays bug tables and charts for a Launchpad project.


Getting Started
===============

```
# git clone git@github.com:ralekseenkov/launchpad-reporting.git
# virtualenv env
# source ./env/bin/activate
# ./install_deps.sh
# ./run_app.sh
```

After that, open http://localhost:4444 in your browser.


How it works
============
- Flask is used as a web frontend
- d3 & nvd3 are used for the charts
- Interation with Launchpad is done through launchpadlib
- The code is optimized to retrieve data from launchpad using the minimum amount of queries. Still, it can take up to 5-10 seconds for a query to complete (for a milestone with hundreds of bugs)
- The results retrieved from Launchpad are cached for 5 minutes. See decorator @ttl_cache


Limitations
===========
- Does not show private bugs, as it requires more complex authentication flow with Launchpad


Screenshots
===========
![alt tag](https://raw2.github.com/ralekseenkov/launchpad-reporting/master/screenshots/release_bug_trends.png)
