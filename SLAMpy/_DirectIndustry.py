from os import path, sep
import arcpy


class IndustryV2(object):
    def __init__(self):
        self.__version__ = '2'
        self.category = 'Sources'
        self.label = 'Industry [v{}]'.format(self.__version__)
        self.description = "Direct nutrient discharges from licensed (IPC and Section 4) industries."
        self.canRunInBackground = False

    def getParameterInfo(self):
        # Define Workspace
        root = path.dirname(path.dirname(path.realpath(__file__)))
        arcpy.env.workspace = root

        # Parameters for Folders Options
        in_gdb = sep.join([root, 'in', 'input.gdb'])

        in_fld = sep.join([root, 'in'])

        out_gdb = arcpy.Parameter(
            displayName="Output Geodatabase",
            name="out_gdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input",
            category='# Folders Settings')
        out_gdb.value = sep.join([root, 'out', 'output.gdb'])

        out_fld = arcpy.Parameter(
            displayName="Output Folder",
            name="out_fld",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input",
            category='# Folders Settings')
        out_fld.value = sep.join([root, 'out'])

        # Parameters Common to All Sources
        project_name = arcpy.Parameter(
            displayName="Name of the Project",
            name="project_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        nutrient = arcpy.Parameter(
            displayName="Nutrient of Interest",
            name="nutrient",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        nutrient.filter.type = "ValueList"
        nutrient.filter.list = ['Nitrogen (N)', 'Phosphorus (P)']

        region = arcpy.Parameter(
            displayName="Region of Interest",
            name="region",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        selection = arcpy.Parameter(
            displayName="Selection within Region",
            name="selection",
            datatype="GPSQLExpression",
            parameterType="Optional",
            direction="Input")
        selection.parameterDependencies = [region.name]

        # Parameters specific to Industry
        in_ipc = arcpy.Parameter(
            displayName="IPC Licences Data",
            name="in_ipc",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            category="Industry Data Settings")
        in_ipc.value = sep.join([in_gdb, 'IPPC_Discharge'])

        in_sect4 = arcpy.Parameter(
            displayName="Section 4 Licences Data",
            name="in_sect4",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            category="Industry Data Settings")
        in_sect4.value = sep.join([in_gdb, 'Sect4_Discharge'])

        return [out_gdb, out_fld,
                project_name, nutrient, region, selection,
                in_ipc, in_sect4]

    def execute(self, parameters, messages):
        """
        :param parameters: list of the 8 parameters in the order as follows:
           [0] nutrient of interest [type: str] {possible values: 'Nitrogen (N)' or 'Nitrogen (P)'}
           [1] path of the feature class for the region of interest [type: str] {required}
           [2] SQL query to select specific location(s) within region [type: str] {optional}
           [3] path of the input feature class of the Licenced 4 Industry data for arable [type: str] {required}
           [4] path of the input feature class of the IPC Industry data for pasture [type: str] {required}
           [5] path of the output feature class for Licenced 4 Industry load [type: str] {required}
           [6] path of the output feature class for IPC Industry load [type: str] {required}
        :param messages: Messages object provided by ArcPy when running the tool

        N.B. If the optional parameters are not used, they must be set to None.
        """

        # retrieve parameters
        out_gdb, out_fld, project_name, nutrient, region, selection, in_ipc, in_sect4 = \
            [p.valueAsText for p in parameters]

        # determine which nutrient to work on
        nutrient = 'N' if nutrient == 'Nitrogen (N)' else 'P'

        # determine which location to work on
        if selection:  # i.e. selection requested
            messages.addMessage("> Selecting requested Location(s) within Region.")
            location = sep.join([out_gdb, project_name + '_SelectedRegion'])
            arcpy.Select_analysis(region, location, selection)
        else:
            location = region

        # run geoprocessing function
        industry_v2_geoprocessing(project_name, nutrient, location, in_ipc, in_sect4, out_gdb, messages)


def industry_v2_geoprocessing(project_name, nutrient, location, in_ipc, in_sect4, out_gdb, messages,
                              out_ipc=None, out_sect4=None):
    """
    :param project_name: name of the project that will be used to identify the outputs in the geodatabase [required]
    :type project_name: str
    :param nutrient: nutrient of interest {possible values: 'N' or 'P'} [required]
    :type nutrient: str
    :param location: path of the feature class for the location of interest [required]
    :type location: str
    :param in_ipc: path of the input feature class of the IPC licensed industry data [required]
    :type in_ipc: str
    :param in_sect4: path of the input feature class of the Section 4 licensed industry data [required]
    :type in_sect4: str
    :param out_gdb: path of the geodatabase where to store the output feature classes [required]
    :type out_gdb: str
    :param messages: object used for communication with the user interface [required]
    :type messages: instance of a class featuring a 'addMessage' method
    :param out_ipc: path of the output feature class for IPC licensed industry load [optional]
    :type out_ipc: str
    :param out_sect4: path of the output feature class for Section 4 licensed industry load [optional]
    :type out_sect4: str
    """
    # calculate load for IPC licences
    messages.addMessage("> Calculating {} load for IPC industries.".format(nutrient))

    if not out_ipc:
        out_ipc = sep.join([out_gdb, project_name + '_{}_IndustryIPC'.format(nutrient)])

    arcpy.Intersect_analysis([location, in_ipc], out_ipc,
                             join_attributes="ALL", output_type="INPUT")

    arcpy.AddField_management(out_ipc, "IPPC_calc", "DOUBLE",
                              field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED")
    arcpy.CalculateField_management(out_ipc, "IPPC_calc",
                                    "!{}_2012_LAM!".format(nutrient),
                                    expression_type="PYTHON_9.3")

    # calculate load for Section 4 licences
    messages.addMessage("> Calculating {} load for Section 4 industries.".format(nutrient))

    if not out_sect4:
        out_sect4 = sep.join([out_gdb, project_name + '_{}_IndustrySect4'.format(nutrient)])

    arcpy.Intersect_analysis([location, in_sect4], out_sect4,
                             join_attributes="ALL", output_type="INPUT")

    arcpy.AddField_management(out_sect4, "Sect4_Flow", "DOUBLE",
                              field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED")
    arcpy.CalculateField_management(out_sect4, "Sect4_Flow",
                                    expression="flow",
                                    expression_type="PYTHON_9.3",
                                    code_block="""
                                            if !Flow__m3_d! > 0:
                                                flow = !Flow__m3_d! 
                                            else:
                                                flow = !Discharge_!
                                        """)

    arcpy.AddField_management(out_sect4, "Sect4_ELV", "DOUBLE",
                              field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED")
    arcpy.CalculateField_management(out_sect4, "Sect4_ELV",
                                    expression="elv",
                                    expression_type="PYTHON_9.3",
                                    code_block="""
                                            nutrient = '{}'
                                            if nutrient == 'N':
                                                elv = float(max([!TON_ELV!, !TN_ELV!, !NO3_ELV!, 
                                                                 !NH3_ELV!, !NH4_ELV!, !NO2_ELV!]))
                                            else:
                                                elv = float(max([!TP_ELV!, !PO4_ELV!]))
                                        """.format(nutrient))

    arcpy.AddField_management(out_sect4, "Sect4_Load", "DOUBLE",
                              field_is_nullable="NULLABLE", field_is_required="NON_REQUIRED")
    arcpy.CalculateField_management(out_sect4, "Sect4_Load",
                                    expression="!Sect4_ELV! * 0.25 * !Sect4_Flow! * 0.365",
                                    expression_type="PYTHON_9.3")
