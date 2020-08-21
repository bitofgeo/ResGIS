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
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterFeatureSink)
import processing
import os
import numpy as np
import datetime
import math
import glob


class ExampleProcessingAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    INPUT_PROFILES = 'INPUT_PROFILES'
    INPUT_DEM = 'INPUT_DEM'
    SPACING = 'SPACING'
    PARENT_DIR = 'PARENT_DIR'
    ADDITIONAL_CRS = 'ADDITIONAL_CRS'
    ADD_NULL_VAL = 'ADD_NULL_VAL',
    MEDIAN_WINDOW = 'MEDIAN_WINDOW'
    IVP_FILE = 'IVP_FILE'
    INVERT_FLAG = 'INVERT_FLAG'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ExampleProcessingAlgorithm()

    def name(self):
        return 'geophygis:export'

    def displayName(self):
        return self.tr('Export v. 1.0')

    def group(self):
        return self.tr('GeophyGIS')

    def groupId(self):
        return 'geophygis'

    def shortHelpString(self):
        return self.tr("Export module for GeophyGIS by bitgeo. For further help see documentation provided.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('ERT profiles:'),
                [QgsProcessing.TypeVectorLine]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterRasterLayer(
            'INPUT_DEM',
            'Digital Elevation Model:',
            )
        
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
            'SPACING',
            'Electode spacing:',
            type = QgsProcessingParameterNumber.Double,
            defaultValue = 50,
            minValue = 0.5,
            maxValue = 50
            )
        
        )
        
        self.addParameter(
            QgsProcessingParameterFile(
            'PARENT_DIR',
            'Parent directory:',
            defaultValue = 'D:/Dokumenty/Obowiazki/GeoVolt/S74/DANE',
            behavior = QgsProcessingParameterFile.Folder
            )
        )
        
        self.addParameter(
            QgsProcessingParameterCrs(
            'ADDITIONAL_CRS',
            'Additional CRS for recalculation:',
            defaultValue = 'EPSG:4326',
            optional = True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
            'ADD_NULL_VAL',
            'Additional null value to replace:',
            type = QgsProcessingParameterNumber.Integer,
            defaultValue = None,
            optional = True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
            'MEDIAN_WINDOW',
            'Provide window size for median filtering:',
            type = QgsProcessingParameterNumber.Integer,
            optional = True,
            defaultValue = None,
            minValue = 3,
            maxValue = 13                
            )
        
        )
        
        self.addParameter(
            QgsProcessingParameterFile(
            'IVP_FILE',
            '*.ivp file to create batch processing file:',
            behavior = QgsProcessingParameterFile.File,
            extension = 'ivp',
            optional = True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
            'INVERT_FLAG',
            'Try to invert dataset? [beta]'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsVectorLayer(
            parameters,
            self.INPUT,
            context
        )
        
        feedback.pushInfo(str(type(source)))
        
        dem_layer = self.parameterAsRasterLayer(
            parameters,
            self.INPUT_DEM,
            context
        )
        
        spacing = self.parameterAsDouble(
            parameters,
            self.SPACING,
            context
        )
        
        parent_dir_path = self.parameterAsString(
            parameters,
            self.PARENT_DIR,
            context
        )
        
        additional_CRS = self.parameterAsCrs(
            parameters,
            self.ADDITIONAL_CRS,
            context
        )
        
        null_value2 = self.parameterAsInt(
            parameters,
            'ADD_NULL_VAL',
            context
        )
        
        median_window_size = self.parameterAsInt(
            parameters,
            self.MEDIAN_WINDOW,
            context
        )
        
        ivp_path = self.parameterAsString(
            parameters,
            self.IVP_FILE,
            context
        )
        
        inversion_flag = self.parameterAsBool(
            parameters,
            self.INVERT_FLAG,
            context
        )

        if source.isValid() == False:
            raise QgsProcessingException('Invalid vector input')
            
        if dem_layer.isValid() == False:
            raise QgsProcessingException('Invalid vector input')
            
        input_CRS_ID = source.sourceCrs().authid()
        additional_CRS_ID = additional_CRS.authid()
        
        x_fieldname = 'x_' + input_CRS_ID
        y_fieldname = 'y_' + input_CRS_ID
        x_reprojected_fieldname = 'x_' + additional_CRS_ID
        y_reprojected_fieldname = 'y_' + additional_CRS_ID
        x_reprojected_formula = "round(x(transform($geometry," + "'" + input_CRS_ID + "'" + "," + "'" + additional_CRS_ID + "'" + ")),2)"
        y_reprojected_formula = "round(y(transform($geometry," + "'" + input_CRS_ID + "'" + "," + "'" + additional_CRS_ID + "'" + ")),2)"
        
        points_alines = processing.run("qgis:pointsalonglines", {'INPUT':source, 'DISTANCE':spacing, 'START_OFFSET': 0, 'END_OFFSET': 0, 'OUTPUT':'memory:'})
        pts_with_DEM = processing.run("qgis:rastersampling", {'INPUT':points_alines['OUTPUT'], 'RASTERCOPY':dem_layer, 'COLUMN_PREFIX':'DEM', 'OUTPUT':'memory:'})
        calc_x = processing.run("qgis:fieldcalculator", {'INPUT':pts_with_DEM['OUTPUT'], 'FIELD_NAME':x_fieldname, 'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 2, 'NEW_FIELD':True, 'FORMULA':'$x', 'OUTPUT':'memory:'})
        calc_y = processing.run("qgis:fieldcalculator", {'INPUT':calc_x['OUTPUT'], 'FIELD_NAME':y_fieldname, 'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 2, 'NEW_FIELD':True, 'FORMULA':'$y', 'OUTPUT':'memory:'})
        calc_xTransformed = processing.run("qgis:fieldcalculator", {'INPUT':calc_y['OUTPUT'], 'FIELD_NAME':x_reprojected_fieldname, 'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 2, 'NEW_FIELD':True, 'FORMULA': x_reprojected_formula, 'OUTPUT':'memory:'})
        calc_yTransformed = processing.run("qgis:fieldcalculator", {'INPUT':calc_xTransformed['OUTPUT'], 'FIELD_NAME':y_reprojected_fieldname,'FIELD_TYPE': 0, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 2, 'NEW_FIELD':True, 'FORMULA': y_reprojected_formula, 'OUTPUT':'memory:'}, context = context, feedback=feedback)['OUTPUT']

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            calc_yTransformed.fields(),
            calc_yTransformed.wkbType(),
            calc_yTransformed.sourceCrs()
        )
        
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
            
        time_object = datetime.datetime.now()
        time_stamp = "(" + time_object.strftime('%d%m_%H%M%S') + ")"
        
        topo_dir_path = parent_dir_path + "/TOPO_" + time_stamp
        os.mkdir(topo_dir_path)  # stworzenie podfolderu
        
        parent_dir_name = os.path.basename(parent_dir_path)  #stworzenie pliku roboczego tabeli atrybutów
        attab_file = open(topo_dir_path + '\\' + parent_dir_name + '.attab', 'a+')
        topx_file = open(topo_dir_path + '\\' + parent_dir_name + '.top', 'a+')  #stworzenie pliku zbiorczego topografii
        
        features = calc_yTransformed.getFeatures()
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            if (feature["DEM_1"] == -9999 or feature["DEM_1"] == null_value2 or str(feature["DEM_1"]) == "NULL") == False:
                lineout = str(feature['ID']) + "\t" + str(feature["distance"]) + "\t" + str(feature["DEM_1"]) + "\n"
                attab_file.write(lineout)
            
        attab_file.close()
        
        attab_filename = open(topo_dir_path + '\\' + parent_dir_name + '.attab') #tymczasowe rozwiązanie
        raw_attab = np.genfromtxt(topo_dir_path + '\\' + parent_dir_name + '.attab',
                                  delimiter='\t', dtype='string_')  # pobranie danych z pliku
        attab = raw_attab.copy()  # zebranie metadanych o zaimportowanej macierzy
        attab_n, attab_m = attab.shape
        bound_indic = [0]  # boundary indicators - przedziały między profilami w danych
        attab_prof_nam = []
        attab = attab[attab[:, 1].argsort()]  # sortowanie
        attab = attab[attab[:, 0].argsort(kind='mergesort')]

        for j in range(1, attab_n):  # mapowanie granic i nazw do rozdzielenia profili
            if attab[j, 0] != attab[j-1,0]:
                bound_indic.append(j)
                attab_prof_nam.append(attab[j-1,0])
        bound_indic.append(attab_n-1)  # dokładka ostatniej granicy i ostatniej nazwy
        attab_prof_nam.append(attab[j - 1, 0])

        attab_dict = dict.fromkeys(attab_prof_nam, np.array)  # stworzenie słownika

        for i in range(0, len(attab_prof_nam)):  # wypełnienie słownika posorotowanymi danymi
            temp_array = attab[bound_indic[i]:bound_indic[i+1], 1:].astype(np.float32)
            temp_array = temp_array[temp_array[:, 1].argsort()]
            temp_array = temp_array[temp_array[:, 0].argsort(kind='mergesort')]
            column_1 = temp_array[:,1]
            column_0 = temp_array[:,0]
            column_1 = np.atleast_2d(column_1)
            column_0 = np.atleast_2d(column_0)
            if (median_window_size == 0) == False:
                to_RA = column_1.copy()
                RA = column_1.copy()
                len_RA = to_RA.shape[1]
                if median_window_size > len_RA/2:
                    median_window_size = len_RA/2
                    if median_window_size % 2 == 0:
                        median_window_size = median_window_size + 1
                    feedback.pushInfo("Size of window for filtering is too big. Changing window size to " + str(int(median_window_size)) + " probes") #erro
                if median_window_size % 2 == 0:
                    median_window_size = median_window_size + 1
                n_2 = int((median_window_size - 1) / 2)
                for j in range(n_2, len_RA - n_2):
                    RA[0,j] =  round(np.sum(to_RA[0, j - n_2 : j + n_2 + 1]) / median_window_size,2)
                margins = range(1, n_2)
                margin_window_sizes = list(range(3, int(median_window_size), 2))
                for k in margins:
                    median_window_size = margin_window_sizes[k - 1]
                    n_2_margin = int((median_window_size - 1) / 2)
                    RA[0,k] = round(np.sum(to_RA[0,  : k + n_2_margin + 1]) / median_window_size,2)
                for k in margins:
                    median_window_size = margin_window_sizes[k - 1]
                    n_2_margin = int((median_window_size - 1) / 2)
                    kk = -k-1
                    kk1 = kk - n_2_margin
                    RA[0, kk] = round(np.sum(to_RA[0, kk1 :]) / median_window_size,2)
                temp_array_2 = np.append(column_0, RA, axis=0)
                temp_array_3 = np.transpose(temp_array_2)
            else:
                temp_array_3 = temp_array.copy()
            attab_dict[attab_prof_nam[i]] = temp_array_3
        
        
        for prof_name in attab_prof_nam:  # odzyskanie nazwy profilu i przeformatowanie na wlasciwy string
            val_prof_name = str(prof_name)
            val_prof_name = val_prof_name.replace('b', '')
            val_prof_name = val_prof_name.replace("'", "")
            try:
                with open(parent_dir_path + '\\' + val_prof_name + '.dat') as file_open_res:
                    file_res_topo = open(topo_dir_path + '\\' + val_prof_name + '_topo.dat', 'a+')  # stworzenie nowego pliku
                    topx_file.write("TOPO of:" + val_prof_name + "\n")

                    res_data = file_open_res.readlines()  # odczytanie istniejącego pliku z opornościami
                    
                    while res_data[-1].rstrip('\n') == '0':  # wycięcie zer kończących
                        del res_data[-1]
                        
                    res_data.append('2\n')   # dodanie dwójki

                    topo_n, topo_m = attab_dict[prof_name].shape
                    res_data.append(int(topo_n))
                    topo_data = attab_dict[prof_name].tolist()  # przerobienie numpy na listę

                    for i in range (0, len(res_data)):
                        file_res_topo.write(str(res_data[i]))
                    file_res_topo.write('\n')
                    for j in range (0, len(topo_data)):
                        file_res_topo.write(str(topo_data[j][0]) + "\t" + str(round(topo_data[j][-1], 3)) + "\n")
                        topx_file.write(str(topo_data[j][0]) + "\t" + str(round(topo_data[j][-1], 3)) + "\n")
                    file_res_topo.write('0\n0\n0\n0\n0\n')
                    topx_file.write("###\n")

                    file_open_res.close()
                    file_res_topo.close()
            except:
                feedback.pushInfo("Profile not found: " + val_prof_name)

        attab_file.close()
        
        feedback.pushInfo("::" + ivp_path)
        
        if (ivp_path == "") == False:
            dat_files = glob.glob(topo_dir_path + "/*.dat")
            parent_dir = os.path.basename(parent_dir_path)
            numof_dat = len(dat_files)
            numof_bth = math.ceil(numof_dat/40)
            for i in range(0, numof_bth):
                k = 40 * (i + 1)  # obliczenia konieczne do zachowania limitu 40 profili na batch
                if k > numof_dat:
                    k = numof_dat
                batch_file = open(topo_dir_path + "/" + parent_dir + '_' + str(i + 1) + '.bth', 'a+')
                batch_file.write(str(k - i * 40) + "\n")
                batch_file.write("INVERSION PARAMETERS FILES USED\n")
                for j in range(i * 40, k):
                    batch_file.write("DATA FILE " + str(j - i * 40 + 1) + "\n")
                    batch_file.write(str(dat_files[j]) + "\n")
                    batch_file.write(str(dat_files[j]).replace('.dat', '.inv') + "\n")
                    batch_file.write(ivp_path + "\n")
                    j += 1


        if inversion_flag == True:
            res2dinv_path = 'D:\Dokumenty\Obowiazki\GeoVolt\Res2DInv'
            bth_files = glob.glob(topo_dir_path + "\*.bth")   # zebranie wszystkich plików bth
            for file in bth_files:  # pętla wysyłająca do CMD składnię program - plik batch
                os.system(res2dinv_path + ' ' + file)
                feedback.pushInfo(str(bth_files))
            

        return {self.OUTPUT: dest_id}