launchpad-reporting
===================

Convenient web-based frontend for Launchpad. Displays bug tables and charts for a Launchpad project.


Getting Started
===============

```
First, install pip and virtualenv on your system. On Ubuntu it can be done by running "sudo apt-get install python-pip python-virtualenv". You may also consider using virtualenvwrapper script (http://virtualenvwrapper.readthedocs.org/en/latest/). Also you will need to install mongodb. Then:

~$ virtualenv venv  # creating virtualenv
~$ source venv/bin/activate
~$ git clone https://github.com/Mirantis/launchpad-reports-summary.git
~$ cd launchpad-reports-summary
~$ mkdir data  # folder to store mongodb data (you can specify your own)
~$ mongod --dbpath ./data  # this launches mongodb instance. It may take some time first
~$ pip install -r requirements.txt
~$ python syncdb.py
~$ python collect_assignees.py
~$ python main.py run
```

After that, open http://localhost:1111 in your browser.


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
![alt tag](https://raw.githubusercontent.com/Mirantis/launchpad-reports-summary/master/launchpad-reporting/screenshots/release_bug_trends.png)
