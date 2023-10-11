# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ArchesProject
                                 A QGIS plugin
 This plugin links QGIS to an Arches project.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-09-15
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Knowledge Integration
        email                : samuel.scandrett@k-int.co.uk
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QTableView
from qgis.core import QgsProject, QgsVectorLayer, QgsVectorLayerCache
from qgis.gui import (QgsAttributeTableView, 
                      QgsAttributeTableModel, 
                      QgsAttributeTableFilterModel,
                      )

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .arches_project_dialog import ArchesProjectDialog
import os.path

#from shapely import GeometryCollection
import requests
from datetime import datetime


class ArchesProject:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ArchesProject_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Arches Project')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        # Cache connection details to prevent firing duplicate connections
        self.arches_connection_cache = {}
        # Store token data to avoid regenerating every connection
        self.arches_token = {}
        self.arches_graphs_list = []
        

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ArchesProject', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/arches_project/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Arches Project'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Arches Project'),
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = ArchesProjectDialog()

            ## Have everything called in here so multiple connections aren't made when plugin button pressed
            # This way only one connection is made at a time
            self.dlg.tabWidget.setCurrentIndex(0)

            # initiate the current selected layer
            self.map_selection()

            # Connection to Arches instance
            self.dlg.btnSave.clicked.connect(self.arches_connection_save)
            self.dlg.btnReset.clicked.connect(lambda: self.arches_connection_reset(hard_reset=True))

            # Get the map selection and update when changed
            self.iface.mapCanvas().selectionChanged.connect(self.map_selection)

            ## Set "Create resource" to false to begin with and only update once Arches connection made
            self.dlg.createResModelSelect.setEnabled(False)
            self.dlg.createResFeatureSelect.setEnabled(False)
            self.dlg.addNewRes.setEnabled(False)
            self.dlg.resetNewResSelection.setEnabled(False)
                
            # to run when layer is changed in create resource
            self.dlg.createResFeatureSelect.currentIndexChanged.connect(self.update_map_layers)
            # to run when graph is changed in create resource
            self.dlg.createResModelSelect.currentIndexChanged.connect(self.update_graph_options)

            self.dlg.addNewRes.clicked.connect(self.create_resource)
        

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass


    def map_selection(self):
        """Get the Arches Resource from the map"""
        active_layer = self.iface.activeLayer()
        canvas = self.iface.mapCanvas()
        features = active_layer.selectedFeatures()
        print("\nmap selection has been fired because selection changed")
        print("layer:",active_layer, "features:",features)

        if len(features) > 1:
            print("Select one feature")
            return
        elif len(features) == 0:
            print("No feature selected")
            return
        else:
            print("FEATURE SELECTED")
            for f in features:
                if "resourceinstanceid" in f.attributeMap():
                    self.dlg.selectedResUUID.setText(f['resourceinstanceid'])
                    no_rows = len(f.attributes())
                    print(no_rows)
                    no_cols = 2

                    self.dlg.selectedResAttributeTable.setRowCount(no_rows)
                    self.dlg.selectedResAttributeTable.setColumnCount(no_cols)


    def update_map_layers(self):
        selectedLayerIndex = self.dlg.createResFeatureSelect.currentIndex()
        selectedLayer = self.layers[selectedLayerIndex]

    def update_graph_options(self):
        selectedGraphIndex = self.dlg.createResModelSelect.currentIndex()
        selectedGraph = self.arches_graphs_list[selectedGraphIndex]    


    # def refresh_selection(self):
    #     self.dlg.createResModelSelect.clear()
    #     if self.arches_token:
    #         self.dlg.createResConnectionStatus.setText("Connected to Arches instance.")

    #         all_layers = list(QgsProject.instance().mapLayers().values())

    #         # only get vector layers
    #         self.layers = [layer for layer in all_layers if isinstance(layer,QgsVectorLayer)]

    #         self.dlg.createResFeatureSelect.setEnabled(True)
    #         self.dlg.createResFeatureSelect.clear()
    #         self.dlg.createResFeatureSelect.addItems([layer.name() for layer in self.layers])
            
    #         if self.arches_graphs_list:
    #             self.dlg.createResModelSelect.setEnabled(True)
    #             self.dlg.createResModelSelect.addItems([graph["name"] for graph in self.arches_graphs_list])

    #             self.dlg.addNewRes.setEnabled(True)
    #             self.dlg.resetNewResSelection.setEnabled(True)
    #     else:
    #         self.dlg.createResConnectionStatus.setText("Connect to Arches instance from the previous tab.")



    def create_resource(self):
        selectedLayerIndex = self.dlg.createResFeatureSelect.currentIndex()
        selectedLayer = self.layers[selectedLayerIndex]
        selectedGraphIndex = self.dlg.createResModelSelect.currentIndex()
        selectedGraph = self.arches_graphs_list[selectedGraphIndex]

        # Would use shapely to create GEOMETRYCOLLECTION but that'd require users to install the dependency themselves
        # this is the alternative        
        all_features = [feature.geometry().asWkt() for feature in selectedLayer.getFeatures()]

        geomcoll = "GEOMETRYCOLLECTION (%s)" % (','.join(all_features))

        try:
            results = self.save_to_arches(tileid=None,
                                        nodeid = selectedGraph["node_id"],
                                        geometry_collection=geomcoll,
                                        geometry_format=None,
                                        arches_operation="create")
            self.dlg.createResOutputBox.setText("""Successfully created a new resource with the selected geometry.
                                                \nTo continue the creation of your new resource, navigate to...\n%s/resource/%s""" % 
                                              (self.arches_token["formatted_url"], results["resourceinstance_id"]))
        except:
            self.dlg.createResOutputBox.setText("Could not create resource")


    def save_to_arches(self, tileid, nodeid, geometry_collection, geometry_format, arches_operation):
        """Save data to arches resource"""
        if self.arches_token:
            try:
                files = {
                    'tileid': (None, tileid),
                    'nodeid': (None, nodeid),
                    'data': (None, geometry_collection),
                    'format': (None, geometry_format),
                    'operation': (None, arches_operation),
                }
                headers = {"Authorization": "Bearer %s" % (self.arches_token["access_token"])}
                response = requests.post("%s/api/node_value/" % (self.arches_token["formatted_url"]), headers=headers, data=files)
            
                if response.ok == True:
                    arches_created_resource = {"nodegroup_id": response.json()["nodegroup_id"],
                                               "resourceinstance_id": response.json()["resourceinstance_id"],
                                               "tile_id": response.json()["tileid"]}
                    return arches_created_resource
                else:
                    print("Resource creation faiiled with response code:%s" % (response.status_code))

            except:
                print("Cannot create new resource")




    def arches_connection_reset(self, hard_reset):
        """Reset Arches connection"""
        if hard_reset == True:
            # Reset connection inputs
            self.dlg.connection_status.setText("")
            self.dlg.arches_server_input.setText("")
            self.dlg.username_input.setText("")
            self.dlg.password_input.setText("")
        # Reset stored data
        self.arches_connection_cache = {}
        self.arches_token = {}
        self.arches_graphs_list = []
        # Reset Create Resource tab as no longer useable
        self.dlg.createResModelSelect.setEnabled(False)
        self.dlg.createResFeatureSelect.setEnabled(False)
        self.dlg.addNewRes.setEnabled(False)
        self.dlg.resetNewResSelection.setEnabled(False)





    def arches_connection_save(self):
        """Data for connection to Arches project server"""

        # strip and remove ending slash
        def format_url():
            formatted_url = self.dlg.arches_server_input.text().strip()
            if formatted_url[-1] == "/":
                formatted_url = formatted_url[:-1]
            return formatted_url

        # once Oauth registered the clientID can be fetched and used
        def get_clientid(url):
            try:
                files = {
                    'username': (None, self.dlg.username_input.text()),
                    'password': (None, self.dlg.password_input.text()),
                }
                response = requests.post(url+"/auth/get_client_id", data=files)
                clientid = response.json()["clientid"]
                return clientid
            except:
                self.dlg.connection_status.append("Can't get client ID.\n- Check username and password are correct.\n- Check the Arches instance is running.\n- Check the instance has a registered Oauth application.")
                return None
            
        def get_token(url, clientid):
            try:
                files = {
                    'username': (None, self.dlg.username_input.text()),
                    'password': (None, self.dlg.password_input.text()),
                    'client_id': (None, clientid),
                    'grant_type': (None, "password")
                }
                response = requests.post(url+"/o/token/", data=files)
                self.arches_token = response.json()
                self.arches_token["formatted_url"] = url
                self.arches_token["time"] = str(datetime.now())
            except:
                self.dlg.connection_status.append("Can't get token.")

        def get_graphs(url):
            try:
                response = requests.get("%s/graphs/" % (url))
                graphids = [x["graphid"] for x in response.json() if x["graphid"] != "ff623370-fa12-11e6-b98b-6c4008b05c4c"] # sys settings

                for graph in graphids:
                    contains_geom = False
                    req = requests.get("%s/graphs/%s" % (url, graph))
                    if req.json()["graph"]["publication_id"]:   # if graph is published
                        for nodes in req.json()["graph"]["nodes"]:
                            if nodes["datatype"] == "geojson-feature-collection":
                                contains_geom=True
                                nodegroupid = nodes["nodegroup_id"]
                                nodeid = nodes["nodeid"]
                        if contains_geom == True:
                            self.arches_graphs_list.append({
                                "graph_id":graph,
                                "name":req.json()["graph"]["name"],
                                "nodegroup_id": nodegroupid,
                                "node_id": nodeid
                            })
            except:
                pass

        # reset connection status on button press
        self.dlg.connection_status.setText("")

        if self.dlg.arches_server_input.text() == "":
            self.dlg.connection_status.append("Please enter the URL to your Arches project.")
        if self.dlg.username_input.text() == "":    
            self.dlg.connection_status.append("Please enter your username.")
        if self.dlg.password_input.text() == "":
            self.dlg.connection_status.append("Please enter your password.")


        # URL field has data in
        if self.dlg.arches_server_input.text() != "":
            formatted_url = format_url()

            clientid = get_clientid(formatted_url)
            if clientid:
                # If client id NOT None then connection has been made
                # check cache first before firing connection again

                # re-fetch graphs before checking cache as updates may have occurred
                self.arches_graphs_list = []
                get_graphs(formatted_url) 

                if self.arches_connection_cache:
                    if (self.dlg.arches_server_input.text() == self.arches_connection_cache["url"] and
                        self.dlg.username_input.text() == self.arches_connection_cache["username"]):
                        self.dlg.connection_status.append("Connected to Arches instance.")   
                        print("Unchanged inputs")
                        return            

                get_token(formatted_url, clientid)

                self.dlg.connection_status.append("Connected to Arches instance.")                    
                # Store for preventing duplicate connection requests
                self.arches_connection_cache = {"url": self.dlg.arches_server_input.text(),
                                                "username": self.dlg.username_input.text()}
                

                # Create resource tab
                self.dlg.createResModelSelect.clear()
                if self.arches_token:
                    all_layers = list(QgsProject.instance().mapLayers().values())
                    # only get vector layers
                    self.layers = [layer for layer in all_layers if isinstance(layer,QgsVectorLayer)]

                    self.dlg.createResFeatureSelect.setEnabled(True)
                    self.dlg.createResFeatureSelect.clear()
                    self.dlg.createResFeatureSelect.addItems([layer.name() for layer in self.layers])
                    
                    if self.arches_graphs_list:
                        self.dlg.createResModelSelect.setEnabled(True)
                        self.dlg.createResModelSelect.addItems([graph["name"] for graph in self.arches_graphs_list])

                        self.dlg.addNewRes.setEnabled(True)
                        self.dlg.resetNewResSelection.setEnabled(True)

            else:
                # If clientid is None i.e no connection, reset cache and token to {}
                self.arches_connection_reset(hard_reset=False)



            # except:
            #     # Connection couldn't be made so reset everything 
            #     print("in except")
            #     self.dlg.connection_status.append("Could not connect to Arches instance.")
            #     self.arches_token = {}
            #     self.arches_graphs_list = []
            #     return False


