# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProject,
                       QgsVectorLayer,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterString,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterFeatureSink)
import processing
import glob
import os
import re
import datetime


class GeophygisProcessingAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    PARENT_DIR = 'PARENT_DIR'
    INPUT_FLAG = 'INPUT_FLAG'
    PROC_CRS = 'PROC_CRS'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GeophygisProcessingAlgorithm()

    def name(self):
        return 'geophygis:import'

    def displayName(self):
        return self.tr('Import v. 1.0')

    def group(self):
        return self.tr('GeophyGIS')

    def groupId(self):
        return 'geophygis'

    def shortHelpString(self):
        return self.tr("Import module for GeophyGIS by bitgeo. For further help see documentation provided.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                'PARENT_DIR',
                'Parent directory:',
                behavior = QgsProcessingParameterFile.Folder,
                optional = False
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
            'INPUT_FLAG',
            '2dm files present',
            )
        )
        
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                'OUTPUT',
                'Output layer'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):        
        source = self.parameterAsVectorLayer(
            parameters,
            self.INPUT,
            context
        )
        
        parent_dir_path = self.parameterAsString(
            parameters,
            self.PARENT_DIR,
            context
        )
        
        flag2dm = self.parameterAsBool(
            parameters,
            self.INPUT_FLAG,
            context
        )
        
        if source.isValid() == False:
            raise QgsProcessingException('Invalid vector input')
        
        time_object = datetime.datetime.now()
        time_stamp = "(" + time_object.strftime('%d%m_%H%M%S') + ")"
        profile_names = []
        files = glob.glob(parent_dir_path + "/*.dat")
        for i in range(0,len(files)):  # odczytanie nazw profili - ID
            profile_names.append((str(os.path.basename(files[i]))[:-4]).upper())
        data = dict.fromkeys(profile_names, [])
        for key in profile_names:  # iterator po pliku
            with open(parent_dir_path + "/" + key + ".dat") as datfile:
                dat_lines = datfile.readlines()
                dat_data = []
                all_arrays =['Wenner-Alpha', 'Pole-Pole', 'Dipole-dipole', 'Wenner-Beta', 'Wenner-Gamma?','Pole-dipole', 'Schlumberger', 'Equatorial dipole-dipole']
                for i in range(1, len(dat_lines)):
                    dat_line = dat_lines[i].rstrip('\n')  # usunięcie niepotrzebnych n-lineów
                    separator = dat_line[0]
                    dat_line = dat_line.lstrip()
                    if separator == ' ':
                        dat_data.append(int(float(dat_line.split(' ')[0])))  # wyłuskanie pierwszej kolumny
                    else:
                        dat_data.append(int(float(dat_line.split('\t')[0])))  # wyłuskanie pierwszej kolumny
                while dat_data[-1] == 0:  # wycięcie zer kończących
                    del dat_data[-1]
                max_electrode = max(dat_data[5:])
                min_electrode = min(dat_data[5:])
                base_spacing = dat_data[0]
                array_type = dat_data[1]
                if array_type in [1, 3, 4, 5, 6, 7]:  # wyliczenie dlugosci profilu
                    profile_end = max_electrode + 3 * base_spacing - min_electrode
                elif array_type == 2:
                    profile_end = max_electrode + base_spacing - min_electrode
                else:
                    profile_end = -999
            header_data = [profile_end, base_spacing, all_arrays[array_type-1]]  # zapisanie danych z dat do pliku
            datfile.close()
            if flag2dm is True:  #moduł do odczytu danych z plików 2dm
                with open(parent_dir_path + "/" + key + ".2dm") as file:
                    header_buffer = []
                    for i in range(1, 26):
                        header_line = file.readline()  # odczytanie linii pliku
                        header_line = header_line.rstrip('\n')  # odrzucenie wszystkiego po nline
                        header_buffer.append(header_line)
                    if 'Time' in header_buffer[1] != -1:  # Ares-II
                        file_type = [13, 2, 1, 0, 4, 5]
                        for j in file_type:  # operacje porządkujące plik żródłowy
                            header_buffer[j] = header_buffer[j].replace('\t', '')
                            header_buffer[j] = re.sub(r'.*: ', '', header_buffer[j])
                            for l in ['Operator:', 'Note:', 'Profile length:', ' m']:
                                header_buffer[j] = header_buffer[j].replace(l, '')
                            header_data.append(header_buffer[j])
                    else:
                        file_type = [9, 3, 24, 0, 2, 4]  # Ares-3D
                        for j in file_type: # operacje porządkujące plik żródłowy
                            header_buffer[j] = re.sub(r'.*:\t', '', header_buffer[j])
                            header_buffer[j] = re.sub(r'.*: \t', '', header_buffer[j])
                        header_buffer[24] = ''
                        header_data.append(header_buffer[j])
            data[key] = header_data
        parent_dir = os.path.basename(parent_dir_path)
        uri = parent_dir_path + "/" + parent_dir + '_meta' + time_stamp + '.csv'
        file_out = open(uri, 'a+')
        file_out.write("ID;LENGTH;SPACING;ARRAY;field_LENGTH;DATE;TIME;DEVICE;OPERATOR;NOTES\n")
        for key in profile_names:  # eksport wszystkich danych do pliku csv, porządkowanie danych
            line_out = str(data[key])
            line_out = line_out.replace(", ", ";")
            line_out = line_out.replace("'", "")
            line_out = line_out.replace('[', '')
            line_out = line_out.replace(']', '')
            file_out.write(key + ';' + line_out + '\n')
        file_out.close()
        
        feedback.pushInfo('file:///' + uri + '?delimiter=;')
        feedback.pushInfo(str(type(source)))
        feedback.pushInfo(str(type(self.INPUT)))
        feedback.pushInfo(parent_dir_path)
        feedback.pushInfo('CRS is {}'.format(source.sourceCrs().authid()))
        feedback.pushInfo(str(source.sourceCrs().authid()))
        
        azim_text = 'degrees(azimuth(start_point($geometry), end_point($geometry)))'
        dir_text = """if("AZIM" > 337.5 OR "AZIM" <22.5, 'N', if("AZIM" > 22.5 AND "AZIM" <67.5, 'NE', 
        if("AZIM" > 67.5 AND "AZIM" <112.5, 'E', if("AZIM" > 112.5 AND "AZIM" <157.5, 'SE', 
        if("AZIM" > 157.5 AND "AZIM" <202.5, 'S', if("AZIM" > 202.5 AND "AZIM" <247.5, 'SW',
        if("AZIM" > 247.5 AND "AZIM" <292.5, 'W', if("AZIM" > 295.5 AND "AZIM" <337.5, 'NW', 'err'))))))))"""
                    
        csv = QgsVectorLayer('file:///' + uri + '?delimiter=;', 'test', 'delimitedtext')
        merged = processing.run("native:joinattributestable", {'INPUT': source, 'FIELD': 'ID' , 'INPUT_2': csv, 'FIELD_2': 'ID', 'METHOD': 1, 'OUTPUT':'memory:'})
        calc_len = processing.run("qgis:fieldcalculator", {'INPUT': merged['OUTPUT'], 'FIELD_NAME':'GIS_LENGTH', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 1, 'NEW_FIELD':True, 'FORMULA': '$length', 'OUTPUT':'memory:'})
        calc_err = processing.run("qgis:fieldcalculator", {'INPUT': calc_len['OUTPUT'], 'FIELD_NAME':'LEN_ERR_[%]', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 2, 'NEW_FIELD':True, 'FORMULA': 'abs("LENGTH"-"GIS_LENGTH")/"LENGTH"*100', 'OUTPUT':'memory:'})
        calc_azim = processing.run("qgis:fieldcalculator", {'INPUT': calc_err['OUTPUT'], 'FIELD_NAME':'AZIM', 'FIELD_TYPE': 1, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 0, 'NEW_FIELD':True, 'FORMULA': azim_text , 'OUTPUT':'memory:'})
        calc_dir = processing.run("qgis:fieldcalculator", {'INPUT': calc_azim['OUTPUT'], 'FIELD_NAME':'DIRECTION', 'FIELD_TYPE' : 2, 'FIELD_LENGTH':10, 'FIELD_PRECISION': 0, 'NEW_FIELD':True, 'FORMULA': dir_text, 'OUTPUT':'memory:'}, context = context, feedback=feedback)['OUTPUT']
        
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            calc_dir.fields(),
            calc_dir.wkbType(),
            calc_dir.sourceCrs()
        )
        
        uri_docsheet = parent_dir_path + "/" + parent_dir + '_docsheet_' + time_stamp + '.csv'
        file_docsheet = open(uri_docsheet, 'a+')  # tworzymy nowy csv
        file_docsheet.write('ID\tGIS_LENGHTH\tLENHGTH\tARRAY\tSPACING\tDIRECTION\n')
        
        features = calc_dir.getFeatures()
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            lineout = str(feature['ID']) + "\t" + str(round(float(feature['GIS_LENGTH']),2)) + "\t" + str(feature['LENGTH']) + "\t" + str(feature['ARRAY']) + "\t" + str(feature['SPACING']) + "\t" + str(feature['DIRECTION'] + "\n")
            file_docsheet.write(lineout)
        
        return {self.OUTPUT: dest_id}
