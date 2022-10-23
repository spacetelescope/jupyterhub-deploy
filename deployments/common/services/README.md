# Announcements

A prototype notification system has been implemented as a JupyterHub managed service.

Based on a lab extension,  each notebook session periodically queries a Tornado server for new announcements which are displayed in real time in a menu at the bottom of the notebook window.   This enables sending critical messages directly to logged in users.

Announcements can be global (sent to all users) or sent only to a particular user.

Announcements have severity levels similar to log severities:  info, warning, error, critical, ...

Announcements witch are more severe than info result in a pop-up window appearing in a user's notebook session.

The code for the notification system consists of 3 basic parts:

- the Tornado service defined here: spacetelescope/jupyterhub-deploy/deployments/common/services/announcements.py
- the admin client defined here: spacetelescope/jupyterhub-deploy/tools/announce
- the lab extension defined here:  https://github.com/jaytmiller/nersc-refresh-announcements/tree/octarine-updates

The EFS user level quota system automatically outputs warnings and quota status to the Tornado server for distribution to the corresponding user.

An admin client (announce) can be run on CI-nodes to push arbitrary announcements to the Tornado service.   Run --help or read the script to figure out the parameters.

Announcements are not currently persistent so restarting the hub/service will cause it to erase the known announcements.

Only the last 5 announcements of each kind,  global or per-user,  are retained by the Tornado service.

See the services source code here for the most current documentation:
   spacetelescope/jupyterhub-deploy/deployments/common/services/README.md
