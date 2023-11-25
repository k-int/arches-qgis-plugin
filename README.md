# Arches QGIS Plugin

Connect to an Arches project to create new resources or edit existing Arches resource geometries using QGIS layers.

## Prerequisites
1. A running Arches instance, accessible via a public domain or IP.
2. An Arches user login with permissions to enter data or create resources.
3. A registered oauth application and client ID entered into settings.py (or settings_local.py) - see the [following documentation link](https://arches.readthedocs.io/en/stable/developing/reference/api/#register-an-oauth-application) for more information on registering oauth2 applications.  

## Installation
Currently the plugin is still in development and thus "experimental" so cannot be downloaded from the QGIS plugin menu. 
To install the plugin, instead follow the following instructions. Be aware that the plugin is currently experimental so there may be some unknown issues/bugs and the creators of the plugin can not be held accountable for any problems that may occur.
1. Clone this repo using `git clone` into your QGIS plugins directory, under your QGIS user. For Windows users this path will look as such: `C:\Users\USERNAME\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
2. Head to the QGIS Plugins tab and select "Manage and install plugins...".
3. Select Arches project from the list of all plugins.
