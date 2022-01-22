import json
import os
import random
import re
import subprocess
import xml.etree.ElementTree as Etree
from shutil import rmtree
from enum import Enum

from InputReader import InputReader, m_ModifiedMDEFLocation, m_CompareTwoRevisions
from GenUtility import assure, getEnvVariableValue, checkFilesInDir, copyFilesInDir, PerforceUtility


class TestSuites(Enum):
    Integration = 'Integration'
    SP = 'SP'
    DML = 'DML'
    SQL = 'SQL'


class TestSets(Enum):
    SQL_SELECT_ALL = ['SQL_SELECT_ALL']
    SQL_PASSDOWN = ['SQL_PASSDOWN']
    SQL_SP = ['SQL_SP']
    SQL_AND_OR = ['SQL_AND_OR']
    SQL_FUNCTION_1TABLE = ['SQL_FUNCTION_1TABLE']
    SQL_GROUP_BY = ['SQL_GROUP_BY']
    SQL_IN_BETWEEN = ['SQL_IN_BETWEEN']
    SQL_LIKE = ['SQL_LIKE']
    SQL_ORDER_BY = ['SQL_ORDER_BY', 'SQL_ORDER']
    SQL_SELECT_TOP = ['SQL_SELECT_TOP']
    SQL_COLUMNS_1TABLE = ['COLUMNS_1TABLE']


# Global Variables
m_TouchStoneAssets = ['Touchstone.exe', 'sbicudt58_64.dll', 'sbicuuc58d_64.dll']
m_TouchStone = 'Touchstone.exe'
m_TouchStoneOutput = 'TouchStoneOutput'
m_OutputFolder = 'Output'
m_EnvsFolder = 'Envs'
m_TestEnv = 'TestEnv.xml'
m_TestSuite = 'TestSuite.xml'
m_TestFilesExtension = '.xml'
m_TestSets = 'TestSets'
m_ResultSets = 'ResultSets'
TOUCHSTONE_DIR = getEnvVariableValue('TOUCHSTONE_DIR')


class MDEF:
    # MDEF Variables
    m_StoredProcedures = 'StoredProcedures'
    m_Tables = 'Tables'
    m_TableName = 'TableName'
    m_Name = 'Name'
    m_Column = 'Column'
    m_Columns = 'Columns'
    m_MetaData = 'Metadata'
    m_SQLType = 'SQLType'
    m_APIAccesses = ['ReadAPI', 'CreateAPI', 'UpdateAPI', 'DeleteAPI']
    m_APIAccess = 'APIAccess'
    m_ColumnRequirements = 'ColumnRequirements'
    m_VirtualTables = 'VirtualTables'
    m_ResultTable = 'ResultTable'
    m_ParentColumn = 'ParentColumn'
    m_Passdownable = 'Passdownable'

    def __init__(self, inFilePath: str = None, withColumns: bool = False, inFileContent: dict = None):
        if inFilePath is not None:
            if len(inFilePath) > 0 and os.path.exists(inFilePath):
                with open(inFilePath, 'r') as file:
                    self.MDEFPath = inFilePath
                    self.MDEFContent = json.load(file)
                    self.TableNames = dict()
                    self.VirtualTableNames = list()
                    self.MDEFStoredProcedures = self.parseStoredProcedures(withColumns)
                    self.Tables = self.parseTables(withColumns)
            else:
                raise FileNotFoundError(f"{inFilePath} is an invalid location")
        else:
            if inFileContent is not None:
                self.MDEFPath = None
                self.MDEFContent = inFileContent
                self.TableNames = dict()
                self.VirtualTableNames = list()
                self.MDEFStoredProcedures = self.parseStoredProcedures(withColumns)
                self.Tables = self.parseTables(withColumns)
            else:
                raise ValueError(f"Invalid MDEF Content provided")

    def findDifference(self, inMDEF):
        """
        Finds the difference in Tables and Stored Procedures with respect to passed MDEF Content \n
        :param inMDEF: Another MDEF Instance to compare in order to find the difference between both
        :return: Returns the difference between both files in the form of MDEF Instance
        """
        if inMDEF is None:
            return None
        mdefDiff = dict()

        # Compare Stored Procedures
        if len(self.MDEFStoredProcedures) > 0 and len(inMDEF.MDEFStoredProcedures) > 0:
            mdefDiff[MDEF.m_StoredProcedures] = list()
            index = 0
            for storedProcName in self.MDEFStoredProcedures:
                if storedProcName not in inMDEF.MDEFStoredProcedures:
                    mdefDiff[MDEF.m_StoredProcedures].append(self.MDEFContent[MDEF.m_StoredProcedures][index])
                index += 1

        # Compare Tables
        if len(self.Tables) > 0 and len(inMDEF.Tables) > 0:
            mdefDiff[MDEF.m_Tables] = list()
            index = 0
            for table in self.MDEFContent[MDEF.m_Tables]:
                if assure(table, MDEF.m_TableName) not in inMDEF.TableNames:
                    mdefDiff[MDEF.m_Tables].append(self.MDEFContent[MDEF.m_Tables][index])
                index += 1

        return mdefDiff if len(mdefDiff[MDEF.m_Tables]) > 0 and len(mdefDiff[MDEF.m_StoredProcedures]) > 0 else None

    def parseStoredProcedures(self, withColumns: bool = False):
        """Parses Stored Procedures"""
        if assure(self.MDEFContent, MDEF.m_StoredProcedures, True) and len(
                self.MDEFContent[MDEF.m_StoredProcedures]) > 0:
            mdefStoredProcedures = list()
            if withColumns:
                for storedProc in self.MDEFContent[MDEF.m_StoredProcedures]:
                    columns = list()
                    if assure(storedProc, MDEF.m_ResultTable):
                        for column in assure(storedProc[MDEF.m_ResultTable], MDEF.m_Columns):
                            columns.append({
                                assure(column, MDEF.m_Name): assure(column[MDEF.m_MetaData], MDEF.m_SQLType) if assure(
                                    column, MDEF.m_MetaData) else None
                            })
                        mdefStoredProcedures.append({
                            assure(storedProc, MDEF.m_Name): columns
                        })
            else:
                for storedProc in self.MDEFContent[MDEF.m_StoredProcedures]:
                    mdefStoredProcedures.append(assure(storedProc, MDEF.m_Name))

            return mdefStoredProcedures

    def parseTables(self, withColumns: bool = False):
        """Parses Tables"""
        if assure(self.MDEFContent, MDEF.m_Tables) and len(self.MDEFContent[MDEF.m_Tables]) > 0:
            mdefTables = list()
            for table in self.MDEFContent[MDEF.m_Tables]:
                if assure(table, MDEF.m_TableName) in mdefTables:
                    raise Exception(
                        f"Error: {self.MDEFPath} contains more than one table with name {table[MDEF.m_TableName]}"
                    )
                else:
                    columns = dict()
                    passdownableColumns = list()
                    if withColumns:
                        if len(assure(table, MDEF.m_Columns)) > 0:
                            for column in table[MDEF.m_Columns]:
                                if assure(column, MDEF.m_Passdownable):
                                    passdownableColumns.append(assure(column, MDEF.m_Name))
                                columns[assure(column, MDEF.m_Name)] = assure(column[MDEF.m_MetaData], MDEF.m_SQLType) \
                                    if assure(column, MDEF.m_MetaData) else None

                    if assure(table, MDEF.m_APIAccess):
                        apiAccesses = list()
                        for apiAccess in table[MDEF.m_APIAccess]:
                            if apiAccess in MDEF.m_APIAccesses:
                                columns_req = assure(table[MDEF.m_APIAccess][apiAccess], MDEF.m_ColumnRequirements,
                                                     True)
                                apiAccesses.append({
                                    apiAccess: columns_req if columns_req else []
                                })
                        mdefTables.append({
                            MDEF.m_Name: table[MDEF.m_TableName],
                            MDEF.m_Columns: columns,
                            MDEF.m_APIAccess: apiAccesses
                        })
                        self.TableNames[table[MDEF.m_TableName]] = passdownableColumns \
                            if len(passdownableColumns) > 0 else None
                    self.parseVirtualTables(table, mdefTables, withColumns)

            return mdefTables

    def parseVirtualTables(self, inTable: dict, inMDEFTables: list, withColumns: bool = False):
        """Parses Virtual Tables"""
        if assure(inTable, MDEF.m_VirtualTables, True) and len(inTable[MDEF.m_VirtualTables]) > 0:
            for virtualTable in inTable[MDEF.m_VirtualTables]:
                if assure(virtualTable, MDEF.m_TableName) in inMDEFTables:
                    raise Exception(f"Error: {self.MDEFPath} contains more than one table "
                                    f"with name {virtualTable[MDEF.m_TableName]}")
                else:
                    columns = dict()
                    if withColumns and len(assure(virtualTable, MDEF.m_Columns)) > 0:
                        for column in virtualTable[MDEF.m_Columns]:
                            if MDEF.m_ParentColumn in column:
                                columnIndex = 0
                                for tableColumn, tableColumnType in inMDEFTables[-1][MDEF.m_Columns].items():
                                    if columnIndex == int(column[MDEF.m_ParentColumn]):
                                        columns[tableColumn] = tableColumnType
                                        break
                                    columnIndex += 1
                            else:
                                columns[assure(column, MDEF.m_Name)] = assure(column[MDEF.m_MetaData], MDEF.m_SQLType) \
                                    if assure(column, MDEF.m_MetaData) else None

                    inMDEFTables.append({
                        MDEF.m_Name: virtualTable[MDEF.m_TableName],
                        MDEF.m_Columns: columns,
                        'Virtual': True
                    })
                    self.VirtualTableNames.append(virtualTable[MDEF.m_TableName])
                    self.parseVirtualTables(virtualTable, inMDEFTables, withColumns)


class TestWriter:

    @staticmethod
    def writeTestEnv(inTestEnvLoc: str, inConnectionString: str):
        """
        Prepares the Test Env File at the specified location \n
        :param inTestEnvLoc: Location to write Test Environment File
        :param inConnectionString: Connection String
        :return: Returns True if written successfully else False
        """
        if os.path.exists(inTestEnvLoc):
            if len(inConnectionString) > 0:
                with open(os.path.join(inTestEnvLoc, m_TestEnv), 'w') as file:
                    file.write('<?xml version="1.0" encoding="utf-8"?>\n')
                    file.write('<TestEnvironment>\n')
                    file.write(f"\t<ConnectionString>{inConnectionString}</ConnectionString>\n")
                    file.write('\t<_Monitor>\n')
                    file.write('\t\t<GenerateResults>true</GenerateResults>\n')
                    file.write('\t\t<timeout>20</timeout>\n')
                    file.write('\t\t<maxConsecutiveTimeout>15</maxConsecutiveTimeout>\n')
                    file.write('\t\t<maxAccumulatedTimeout>50</maxAccumulatedTimeout>\n')
                    file.write('\t</_Monitor>\n')
                    file.write('\t<SqlWcharEncoding>UTF-32</SqlWcharEncoding>\n')
                    file.write('</TestEnvironment>')
                return True
            else:
                print('Error: Empty Connection String passed')
                return False
        else:
            print('Error: Incorrect Test Env Location')
            return False

    @staticmethod
    def writeTestSuites(inRequiredTestSuites: dict):
        """
        Prepares Testsuite Folders and writes `TestSuite.xml` within the folder \n
        :param inRequiredTestSuites: A Dictionary having Testsuite as a key and list of test-sets as value
        :return: Returns True if written successfully else False
        """
        outputFolderLoc = os.path.abspath(m_OutputFolder)
        if os.path.exists(outputFolderLoc):
            for testSuite, testSets in inRequiredTestSuites.items():
                with open(os.path.join(os.path.join(outputFolderLoc, testSuite), m_TestSuite), 'w') as file:
                    file.write('<TestSuite Name="SQL Test">\n')
                    for test_set in testSets:
                        file.write(f"\t<TestSet Name=\"{test_set}\" "
                                   f"SetFile=\"{testSuite}/TestSets/{test_set}{m_TestFilesExtension}\">\n")
                        file.write('\t\t<!--\n')
                        file.write('\t\t<Exclusion StartID="6" EndID="6">Exclusion reason</Exclusion>\n')
                        file.write('\t\t<Ignorable StartID="6" EndID="6">Ignorable reason</Ignorable>\n')
                        file.write('\t\t-->\n')
                        file.write('\t</TestSet>\n')
                    file.write('\t<GenerateResults>true</GenerateResults>\n')
                    file.write(f"\t<BaselineDirectory>{testSuite}\\ResultSets</BaselineDirectory>\n")
                    file.write('</TestSuite>')
            return True
        else:
            print('Error: Incorrect Test Suite Location')
            return False

    @staticmethod
    def writeTestSets(inRequiredTestSuites: dict, inMdefDiff: MDEF, inExternalArgs: dict, onlySelectAll: bool = False,
                      inTableColumnsValues: dict = None):
        """
        Prepares required TestSets for given TestSuites \n
        :param inExternalArgs: External Arguments containing the input params for SP.
        :param inTableColumnsValues: Table Column Values Mapping
        :param onlySelectAll: A Flag to only generate test sets for SQL_SELECT_ALL
        :param inMdefDiff: MDEF Instance
        :param inRequiredTestSuites: A Dictionary having Testsuite as a key and list of test-sets as value
        :return: Returns True if written successfully else False
        """
        if len(inRequiredTestSuites) > 0:
            if not onlySelectAll and (inTableColumnsValues is None or len(inTableColumnsValues) == 0):
                print('Error: Tables Column Values Map must be provided in order to generate Test Cases other than '
                      '`SQL_SELECT_ALL`')
                return False

            hadFailure = False
            for testSuite, testSets in inRequiredTestSuites.items():
                for testSet, startingId in testSets.items():
                    if testSet in TestSets.SQL_SELECT_ALL.value and onlySelectAll:
                        return TestWriter.writeSelectAllTestSets(testSuite, testSet, inMdefDiff, startingId)

                    elif testSet in TestSets.SQL_PASSDOWN.value:
                        hadFailure = not TestWriter.writeSQLPassdownTestsets(testSuite, testSet, inMdefDiff,
                                                                             inTableColumnsValues, startingId)
                    elif testSuite == TestSuites.SP.value and testSet in TestSets.SQL_SP.value:
                        hadFailure = not TestWriter.writeSPTestSets(testSuite, testSet, inExternalArgs[testSuite], startingId)

                    elif testSet in TestSets.SQL_SELECT_TOP.value:
                        hadFailure = not TestWriter.writeSQLSelectTopTestsets(testSuite, testSet,
                                                                              inTableColumnsValues, startingId)
                    elif testSet in TestSets.SQL_AND_OR.value:
                        hadFailure = not TestWriter.writeSQLAndOrTestsets(testSuite, testSet,
                                                                          inTableColumnsValues, startingId)
                    elif testSet in TestSets.SQL_ORDER_BY.value:
                        hadFailure = not TestWriter.writeSQLOrderByTestsets(testSuite, testSet,
                                                                            inTableColumnsValues, startingId)
                    elif testSet in TestSets.SQL_FUNCTION_1TABLE.value:
                        hadFailure = not TestWriter.writeSQLFunctionTestsets(testSuite, testSet,
                                                                             inTableColumnsValues, startingId)
                    elif testSet in TestSets.SQL_GROUP_BY.value:
                        hadFailure = not TestWriter.writeSQLGroupByTestsets(testSuite, testSet, inTableColumnsValues,
                                                                            startingId)
                    elif testSet in TestSets.SQL_IN_BETWEEN.value:
                        hadFailure = not TestWriter.writeSQLInBetweenTestsets(testSuite, testSet, inTableColumnsValues,
                                                                              startingId)
                    elif testSet in TestSets.SQL_LIKE.value:
                        hadFailure = not TestWriter.writeSQLLikeTestsets(testSuite, testSet, inTableColumnsValues,
                                                                         startingId)
                    elif testSet in TestSets.SQL_COLUMNS_1TABLE.value:
                        hadFailure = not TestWriter.writeSQLColumnTableTestsets(testSuite, testSet,
                                                                                inTableColumnsValues, startingId)

                    if hadFailure:
                        print(f"Error: Generation of {testSet} for {testSuite} failed")
                        break

            return not hadFailure
        else:
            print('Error: No Test-Suites selected to prepare')
            return False

    @staticmethod
    def writeSPTestSets(inTestSuite: str, inTestSet: str, inExternalArguments: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_SELECT_All`\n
        :param inTestSet: Name of test case.
        :param inExternalArguments: Stored Procedure Name and Input arguments mapping.
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_SELECT_All` generated successfully else False
        """
        if len(inTestSuite) == 0 or inExternalArguments is None:
            print('Error: Invalid Parameters')
            return False
        else:
            queries = list()
            for name, arg in inExternalArguments.items():
                queries.append('{call ' + name + '(' + arg + ')}')
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)

    @staticmethod
    def writeSelectAllTestSets(inTestSuite: str, inTestSet: str, inMdefDiff: MDEF, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_SELECT_All`\n
        :param inTestSet: Name of test case.
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :param inMdefDiff: Difference of MDEFs as MDEF Instance
        :return: Returns True if all `SQL_SELECT_All` generated successfully else False
        """
        if len(inTestSuite) == 0 or inMdefDiff is None:
            print('Error: Invalid Parameters')
            return False
        else:
            queries = list()
            for table in inMdefDiff.Tables:
                queries.append(f"SELECT * FROM {table[MDEF.m_Name]}")
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)

    @staticmethod
    def writeSQLPassdownTestsets(inTestSuite: str, inTestSet: str, inMdefDiff: MDEF, inTableColumnsValues: dict,
                                 inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_PASSDOWN` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :param inMdefDiff: Difference of MDEFs as MDEF Instance
        :return: Returns True if all `SQL_PASSDOWN` generated successfully else False
        """
        if len(inTestSuite) == 0 or inMdefDiff is None or inTableColumnsValues is None:
            print('Error: Invalid Parameters')
            return False
        else:
            queries = list()
            for tableName, passdownableColumns in inMdefDiff.TableNames.items():
                if passdownableColumns is None or tableName not in inTableColumnsValues:
                    continue
                for columnName in passdownableColumns:
                    for columnValue in inTableColumnsValues[tableName][columnName]:
                        queries.append(f"SELECT * FROM {tableName} WHERE {columnName} = {columnValue}")
                        break
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)

    @staticmethod
    def writeSQLSelectTopTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_SELECT_TOP` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_SELECT_TOP` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            for table_name, columns in inTableColumnsValues.items():
                rowCount = max(list(map(len, columns.values())))
                if rowCount > 0:
                    for columnName in columns:
                        if random.randint(0, 50) % 2 == 0:
                            queries.append(f"SELECT TOP {rowCount % 25} * FROM {table_name} ORDER BY {columnName}")
                        else:
                            queries.append(
                                f"SELECT TOP {rowCount % 25} {columnName} FROM {table_name} ORDER BY {columnName}")
                        break
                else:
                    print(f"Error: Columns for {table_name} could not be parsed correctly from the ResultSets")
                    return False
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLAndOrTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_AND_OR` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_AND_OR` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            index = 0
            for tableName, columns in inTableColumnsValues.items():
                queryCompleted = True
                if len(columns) > 0:
                    query = f"SELECT * FROM {tableName} WHERE "
                    for columnName, columnValues in columns.items():
                        if len(columnValues) >= 2:
                            query += f"{columnName}={columnValues[0]} "
                            queryCompleted = not queryCompleted
                            if queryCompleted:
                                queries.append(query)
                                break
                            else:
                                if index % 2 == 0:
                                    query += 'AND '
                                else:
                                    query += 'OR '
                    index += 1
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLOrderByTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_ORDER_BY` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_ORDER_BY` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            for tableName, columns in inTableColumnsValues.items():
                columnsLen = len(columns)
                requiredColIndex = random.randrange(0, (columnsLen % 10) - 1) if columnsLen % 10 > 1 else 0
                index = 0
                if columnsLen > 0:
                    for columnName in columns:
                        if requiredColIndex == index:
                            if random.randint(0, 5) % 2 == 0:
                                queries.append(f"SELECT * FROM {tableName} ORDER BY {columnName}")
                            else:
                                queries.append(f"SELECT {columnName} FROM {tableName} ORDER BY {columnName}")
                        index += 1
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLColumnTableTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_COLUMNS_1TABLE` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all 'SQL_COLUMNS_1TABLE' generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            for tableName, columns in inTableColumnsValues.items():
                columnsLen = len(columns)
                requiredColIndex = random.randrange(0, (columnsLen % 10) - 1) if columnsLen % 10 > 1 else 0
                index = 0
                firstColumn = None
                if columnsLen > 0:
                    for columnName in columns:
                        if index == 0:
                            firstColumn = columnName
                        if requiredColIndex == index:
                            queries.append(f"SELECT {columnName} FROM {tableName} ORDER BY {firstColumn}")
                        index += 1
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLGroupByTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_GROUP_BY` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_GROUP_BY` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            for tableName, columns in inTableColumnsValues.items():
                if len(columns) > 0:
                    for columnName in columns:
                        if len(columns[columnName]) > 0:
                            queries.append(f"SELECT {columnName} FROM {tableName} GROUP BY {columnName} "
                                           f"HAVING {columnName} = {columns[columnName][0]}")
                            break
                    else:
                        queries.append(f"SELECT {columnName} FROM {tableName} GROUP BY {columnName} "
                                       f"ORDER BY {columnName}")
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLInBetweenTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_IN_BETWEEN` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_IN_BETWEEN` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            for tableName, columns in inTableColumnsValues.items():
                for columnName in columns:
                    totalColumnValues = len(columns[columnName])
                    if totalColumnValues > 2 and any(
                            map(lambda columnValue: isinstance(columnValue, str), columns[columnName])):
                        if totalColumnValues % 2 == 0:
                            queries.append(f"SELECT * FROM {tableName} WHERE {columnName} IN "
                                           f"({', '.join(random.sample(columns[columnName], 2))})")
                        else:
                            queries.append(f"SELECT {columnName} FROM {tableName} WHERE {columnName} IN "
                                           f"({', '.join(random.sample(columns[columnName], 2))})")
                        break
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLLikeTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_LIKE` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_LIKE` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            queryWritten = False
            for tableName, columns in inTableColumnsValues.items():
                for columnName, columnValues in columns.items():
                    for columnVal in columnValues:
                        if isinstance(columnVal, str) and len(columnVal) > 2:
                            queries.append(f"SELECT {columnName} FROM {tableName} WHERE {columnName} LIKE "
                                           f"'%{columnVal[random.randint(1, len(columnVal) - 2)]}{random.choice(['_', '%', ''])}'")
                            queryWritten = True
                        elif isinstance(columnVal, (int, float)):
                            columnValStr = str(columnVal)
                            if len(columnValStr) > 2:
                                queries.append(f"SELECT {columnName} FROM {tableName} WHERE {columnName} LIKE "
                                               f"'%{columnValStr[random.randint(1, len(columnValStr) - 2)]}{random.choice(['_', '%', ''])}'")
                            queryWritten = True
                        break
                    if queryWritten:
                        break
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def writeSQLFunctionTestsets(inTestSuite: str, inTestSet: str, inTableColumnsValues: dict, inStartingID: int = 1):
        """
        Prepares Test Set for `SQL_Function_Table` \n
        :param inTestSet: Name of test case.
        :param inTableColumnsValues: Key Value Pair Containing Table Name & Column Value Map
        :param inStartingID: Starting Id of the test-set to write testcases further
        :param inTestSuite: Name of associated Testsuite
        :return: Returns True if all `SQL_Function_Table` generated successfully else False
        """
        if len(inTestSuite) > 0 and inTableColumnsValues is not None:
            queries = list()
            aggregateFunctions = ['MAX', 'MIN', 'COUNT', 'SUM', 'AVG']
            datetimeRegex = '\'([0-9]+)-([0-9]+)-([0-9]+) ([0-9]+):([0-9]+):([0-9]+).([0-9]+)\''
            for tableName, columns in inTableColumnsValues.items():
                query_written = False
                for columnName, columnValues in columns.items():
                    if any(map(lambda inToken: inToken in columnName.lower(), ['id', 'index'])) or len(columnValues) == 0:
                        pass
                    elif all(map(lambda inVal: isinstance(inVal, (int, float)) and (not isinstance(inVal, (bool, str))),
                                 columnValues)):
                        currOp = random.choice(aggregateFunctions)
                        queries.append(f"SELECT {currOp}({columnName}) AS {currOp}_OF_{columnName.upper()}"
                                       f" FROM {tableName}")
                        break
                    elif not query_written and all(map(lambda inVal: isinstance(inVal, str) and
                                                   re.match(datetimeRegex, inVal) is None, columnValues)):
                        currOp = random.choice(['UCASE', 'LCASE', 'COUNT'])
                        queries.append(f"SELECT {currOp}({columnName}) FROM {tableName}")
                        query_written = True
            return TestWriter._prepareTestSet(inTestSuite, inTestSet, queries, inStartingID)
        else:
            print('Error: Invalid Parameters')
            return False

    @staticmethod
    def _prepareTestSet(inTestSuite: str, inTestSet: str, inQueries: list, inStartingID: int = 1):
        """
        Prepares a new Test-set file for given queries \n
        :param inTestSuite: Name of the Test Suite
        :param inTestSet: Name of the Test Set
        :param inQueries: List of queries
        :param inStartingID: Starting Id for the testcases
        :return: Returns True if Test-set written successfully else False
        """
        if inTestSuite is not None and len(inTestSuite) > 0 and inTestSet is not None and len(inTestSet) > 0:
            testSetPath = os.path.abspath(os.path.join(os.path.join(m_OutputFolder, inTestSuite), m_TestSets))
            if os.path.exists(testSetPath):
                with open(os.path.join(testSetPath, inTestSet + m_TestFilesExtension), 'w') as file:
                    file.write(f"<TestSet Name=\"{inTestSet}\" JavaClass=\"com.simba.testframework.testcases"
                               f".jdbc.resultvalidation.SqlTester\" dotNetClass=\"SqlTester\">\n")
                    for query in inQueries:
                        file.write(f"\t<Test Name=\"SQL_QUERY\" JavaMethod=\"testSqlQuery\" "
                                   f"dotNetMethod=\"TestSqlQuery\" ID=\"{inStartingID}\">\n")
                        file.write(f"\t\t<SQL><![CDATA[{query}]]></SQL>\n")
                        file.write('\t\t<ValidateColumns>True</ValidateColumns>\n')
                        file.write('\t\t<ValidateNumericExactly>True</ValidateNumericExactly>\n')
                        file.write('\t</Test>\n')
                        inStartingID += 1
                    file.write('</TestSet>')
                return True
            else:
                print(f"Error: Path {testSetPath} doesn't exist")
                return False


class TestSetGenerator:
    def __init__(self, inFilePath):
        self.inputFile = InputReader(inFilePath)
        self.inMDEFToGenerateTests = None

    def run(self):
        requiredTestSuites = self.inputFile.getRequiredTestSuites()
        externalArgs = self.inputFile.getExternalArguments()
        if self.setupTestFolders(requiredTestSuites):
            mdefDiff = self.findMDEFDifference()
            if mdefDiff is not None:
                if TestWriter.writeTestSets(requiredTestSuites, mdefDiff, externalArgs, onlySelectAll=True):
                    if ResultSetGenerator.executeTestSuite(TestSuites.Integration.name, TestSets.SQL_SELECT_ALL.name):
                        tableColumnValues = ResultSetGenerator.parseResultSets(
                            mdefDiff, requiredTestSuites[TestSuites.Integration.name][TestSets.SQL_SELECT_ALL.name]
                        )
                        if tableColumnValues is not None and len(tableColumnValues) > 0:
                            return TestWriter.writeTestSets(requiredTestSuites, mdefDiff, externalArgs, False,
                                                            tableColumnValues)
                        else:
                            print('Error: Failed to generate result-sets of `SQL_SELECT_ALL`')
            else:
                print('Warning: Provided MDEFs are identical. No difference found to generate new test-cases.')

    def findMDEFDifference(self):
        mdefDiffMode = self.inputFile.getMDEFDifferenceFindMode()
        if mdefDiffMode == m_CompareTwoRevisions:
            latestMdef, olderMdef = None, None
            mdefLoc = self.inputFile.getMDEFLocation()
            olderMdefRev = self.inputFile.getOlderMDEFRevision()
            newerMdefRev = self.inputFile.getNewerMDEFRevision()
            if olderMdefRev is not None and newerMdefRev is not None:
                olderMdefLoc = PerforceUtility.getRevision(mdefLoc, olderMdefRev)
                olderMdef = MDEF(olderMdefLoc) if olderMdefLoc is not None else None
                newerMdefLoc = PerforceUtility.getRevision(mdefLoc, newerMdefRev)
                newerMdef = MDEF(newerMdefLoc) if newerMdefLoc is not None else None
                mdefDiff = newerMdef.findDifference(olderMdef)
            else:
                latest_mdef_revision_num = PerforceUtility.getLatestRevisionNumber(mdefLoc)
                olderMdefLoc = PerforceUtility.getRevision(mdefLoc, latest_mdef_revision_num - 1)
                olderMdef = MDEF(olderMdefLoc) if olderMdefLoc is not None else None
                latestMdefLoc = PerforceUtility.getRevision(mdefLoc)
                latestMdef = MDEF(latestMdefLoc) if latestMdefLoc is not None else None
                mdefDiff = latestMdef.findDifference(olderMdef)
            if mdefDiff is not None:
                return MDEF(inFileContent=mdefDiff, withColumns=True)
            else:
                print('No Difference found between the specified version of MDEF')
                return None
        else:
            modifedMdefLoc = self.inputFile.getModifiedMDEFLocation()
            if modifedMdefLoc is not None:
                if self.inputFile.isFirstRevision():
                    return MDEF(inFilePath=modifedMdefLoc, withColumns=True)
                else:
                    latestMdefLoc = PerforceUtility.getRevision(self.inputFile.getMDEFLocation())
                    latestMdef = MDEF(latestMdefLoc) if latestMdefLoc is not None else None
                    modifedMdef = MDEF(modifedMdefLoc)
                    mdefDiff = modifedMdef.findDifference(latestMdef)
                if mdefDiff is not None:
                    return MDEF(inFileContent=mdefDiff, withColumns=True)
                else:
                    print('No Difference found between the specified version of MDEF')
                    return None
            else:
                raise Exception(f"{m_ModifiedMDEFLocation} is an invalid value! Provide a correct one.")

    def setupOutputFolder(self):
        """
        Makes a directory name `Output` and puts required files of TouchStone with the same by copying from the
        location environment variable `TOUCHSTONE_DIR` refers \n
        :return: Returns True if `Output` setup successfully else raises an Exception.
        """
        if m_OutputFolder in os.listdir() and os.path.exists(m_OutputFolder) and os.path.isdir(m_OutputFolder):
            return True if checkFilesInDir(os.path.abspath(m_OutputFolder), m_TouchStoneAssets) else \
                copyFilesInDir(TOUCHSTONE_DIR, os.path.abspath(m_OutputFolder), m_TouchStoneAssets)
        else:
            try:
                os.mkdir(m_OutputFolder)
                return copyFilesInDir(TOUCHSTONE_DIR, os.path.abspath(m_OutputFolder), m_TouchStoneAssets)
            except PermissionError as e:
                print('Error:', e)
                return False

    def setupTestFolders(self, inRequiredTestSuites: dict):
        """
        Prepares Envs & TestSuites' Folder \n
        :param inRequiredTestSuites: A Dictionary having Testsuite as a key and list of test-sets as value
        :return: Returns True if succeeded else False
        """
        if self.setupOutputFolder():
            outputFolderPath = os.path.abspath(m_OutputFolder)
            envsFolderPath = os.path.abspath(os.path.join(outputFolderPath, m_EnvsFolder))
            if os.path.exists(envsFolderPath):
                rmtree(envsFolderPath)
            os.mkdir(envsFolderPath)
            if TestWriter.writeTestEnv(envsFolderPath, self.inputFile.getConnectionString()):
                for testSuite in inRequiredTestSuites.keys():
                    currTestSuitePath = os.path.abspath(os.path.join(outputFolderPath, testSuite))
                    if os.path.exists(currTestSuitePath):
                        rmtree(currTestSuitePath)
                    os.mkdir(currTestSuitePath)
                    os.mkdir(os.path.join(currTestSuitePath, m_TestSets))
                    os.mkdir(os.path.join(currTestSuitePath, m_ResultSets))
                return TestWriter.writeTestSuites(inRequiredTestSuites)
            else:
                return False
        else:
            return False


class ResultSetGenerator:
    def __init__(self, in_filepath):
        self.inputFileName = in_filepath
        self.inputFile = InputReader(in_filepath)

    def run(self):
        if TestSetGenerator(self.inputFileName).run():
            for testSuite in self.inputFile.getRequiredTestSuites():
                if not ResultSetGenerator.executeTestSuite(testSuite):
                    print(f"Error: {testSuite} could not be generated!")

    @staticmethod
    def executeTestSuite(inTestSuite: str, withSpecificTestSet: str = None):
        """
        Runs Touchstone test for given testsuite \n
        :param withSpecificTestSet: Name of test-set to run Touchstone for that particular test-set only
        :param inTestSuite: Name of the Testsuite
        :return: True if succeeded else False
        """
        if len(inTestSuite) > 0:
            touchstone_cmd = f"{m_TouchStone} -te {m_EnvsFolder}\\{m_TestEnv} " \
                             f"-ts {inTestSuite}\\{m_TestSuite} -o {inTestSuite}"
            if withSpecificTestSet is not None and len(withSpecificTestSet) > 0:
                touchstone_cmd += f" -rts {withSpecificTestSet}"
            currentDir = os.path.abspath(os.curdir)
            os.chdir(m_OutputFolder)
            subprocess.call(touchstone_cmd)
            os.chdir(currentDir)
            return True if len(os.listdir(os.path.join(os.path.join(m_OutputFolder, inTestSuite), m_ResultSets))) > 0 \
                else False
        else:
            print('Error: Invalid Testsuite Name')

    @staticmethod
    def _convertDataType(inData: str, inSQLtype: str):
        """
        Converts given string data into provided data type \n
        :param inData: Data as String to convert
        :param inSQLtype: SQLType to convert data accordingly
        :return: Returns Data with Converted data type
        """
        if inSQLtype in ['SQL_WVARCHAR', 'SQL_TYPE_TIMESTAMP', 'SQL_WLONGVARCHAR']:
            return f"\'{str(inData)}\'"
        elif inSQLtype == 'SQL_BIT':
            return bool(inData)
        elif inSQLtype == 'SQL_INTEGER':
            return int(inData)
        elif inSQLtype == 'SQL_DOUBLE':
            return float(inData)
        else:
            return f"\'{str(inData)}\'"

    @staticmethod
    def parseResultSets(inMdefDiff: MDEF, inStartingID: int = 1):
        """
        Parses the `Result-sets` generated and maps to its relevant columns \n
        :param inMdefDiff: MDEF Difference as MDEF Instance
        :param inStartingID: Starting Testcase Id for `SQL_SELECT_ALL` Testset
        :return: Returns Table Columns Values Mapping
        """
        if inMdefDiff is not None:
            resultSetsPath = os.path.abspath(os.path.join(os.path.join(m_OutputFolder, TestSuites.Integration.name),
                                                          m_ResultSets))
            totalResultSets = len(inMdefDiff.Tables)
            etree = None
            tableColumnValues = dict()
            for testCaseId in range(inStartingID, inStartingID + totalResultSets):
                if os.path.exists(os.path.join(resultSetsPath, f"{TestSets.SQL_SELECT_ALL.name}-SQL_QUERY-"
                                                               f"{testCaseId}{m_TestFilesExtension}")):
                    invalidRowDesc = True
                    rowCount = 0
                    with open(os.path.abspath(os.path.join(resultSetsPath, f"{TestSets.SQL_SELECT_ALL.name}-SQL_QUERY-"
                                                                           f"{testCaseId}{m_TestFilesExtension}"))) as file:
                        etree = Etree.fromstring(file.read().strip())
                        rowDescriptions = None
                        for child in etree.iter('RowDescriptions'):
                            rowDescriptions = child
                            invalidRowDesc = not invalidRowDesc
                            rowCount = int(child.attrib.get('RowCount'))
                        if invalidRowDesc:
                            print('More than one RowDescriptions found in the resultset')
                            return None
                        if rowCount > 0:
                            rowCount %= 30
                            currTableName = inMdefDiff.Tables[testCaseId - inStartingID][MDEF.m_Name]
                            tableColumnValues[currTableName] = dict()
                            columnCount = 0
                            for column in etree.iter('Column'):
                                columnCount += 1
                                columnName = column[0].text.strip()
                                columnType = column[1].attrib.get('Type').strip()
                                tableColumnValues[currTableName][columnName] = list()
                                currColumnValues = set()
                                if columnName in inMdefDiff.Tables[testCaseId - inStartingID][MDEF.m_Columns]:
                                    for i in range(1, rowCount + 1):
                                        columnValue = rowDescriptions[i - 1][columnCount - 1]
                                        if not assure(columnValue.attrib, 'IsNull', ignoreError=True) and \
                                                columnValue.text is not None and columnValue.text.strip() != 'none' and \
                                                len(columnValue.text.strip()) > 0:
                                            currColumnValues.add(
                                                ResultSetGenerator._convertDataType(columnValue.text.strip(), columnType)
                                            )
                                    tableColumnValues[currTableName][columnName] = list(currColumnValues)
                                else:
                                    print('Error: Column Name mismatched')
                                    return None
                            if columnCount != len(inMdefDiff.Tables[testCaseId - inStartingID][MDEF.m_Columns]):
                                print(
                                    'Error: Column Count mismatched! There might be duplicate columns in ' + currTableName)
                                return None
                else:
                    print('Error: Invalid Path', os.path.join(resultSetsPath, f"{TestSets.SQL_SELECT_ALL.name}-SQL_QUERY-"
                                                               f"{testCaseId}{m_TestFilesExtension}"), 'doesn\'t exist!')
                    return None
            return tableColumnValues
