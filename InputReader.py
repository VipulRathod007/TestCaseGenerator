import json
import os

from GenUtility import assure, getEnvVariableValue

# Global Variable
m_ConnectionString = 'ConnectionString'
m_DifferenceFindMode = 'DifferenceFindMode'
m_CompareTwoRevisions = 'CompareTwoRevisions'
m_ExternalArguments = 'ExternalArguments'
m_ModifiedMDEFLocation = 'ModifiedMDEFLocation'
m_IsFirstRevision = 'IsFirstRevision'
m_PerforceLocation = 'PerforceLocation'
m_MDEFLocation = 'MDEFLocation'
m_TestDefinitionsLocation = 'TestDefinitionsLocation'
m_TestSuite = 'TestSuite'

# Perfoce Variables
P4_ROOT = 'P4_ROOT'
P4USER = 'P4USER'
P4CLIENT = 'P4CLIENT'
P4PORT = 'P4PORT'


class InputReader:
    """
    Represents the Input Reader.
    """

    def __init__(self, in_filepath: str):
        if os.path.exists(in_filepath):
            with open(in_filepath, 'r') as file:
                in_file = json.load(file)

            self.inConnectionString = assure(in_file, m_ConnectionString)
            if assure(in_file, m_DifferenceFindMode):
                if assure(in_file[m_DifferenceFindMode], m_CompareTwoRevisions) and \
                        (len(in_file[m_DifferenceFindMode][m_CompareTwoRevisions]) == 2):
                    self.inDifferenceFindMode = m_CompareTwoRevisions
                    revision = in_file[m_DifferenceFindMode][m_CompareTwoRevisions][0]
                    anotherRevision = in_file[m_DifferenceFindMode][m_CompareTwoRevisions][1]
                    if revision < anotherRevision:
                        self.inOlderMDEFVersion = revision
                        self.inNewerMDEFVersion = anotherRevision
                    elif revision > anotherRevision:
                        self.inOlderMDEFVersion = anotherRevision
                        self.inNewerMDEFVersion = revision
                    else:
                        raise Exception(f"Error: Invalid Values for `{m_CompareTwoRevisions}`. "
                                        "MDEF Revision Numbers must be different.")
                elif assure(in_file[m_DifferenceFindMode], m_ModifiedMDEFLocation) and \
                        len(in_file[m_DifferenceFindMode][m_ModifiedMDEFLocation]) > 0:
                    self.inDifferenceFindMode = m_ModifiedMDEFLocation
                    if os.path.exists(in_file[m_DifferenceFindMode][m_ModifiedMDEFLocation]):
                        self.inModifiedMDEFLocation = in_file[m_DifferenceFindMode][m_ModifiedMDEFLocation]
                        self.inFirstRevision = assure(in_file[m_DifferenceFindMode], m_IsFirstRevision)
                    else:
                        raise FileNotFoundError(f"{in_file[m_DifferenceFindMode][m_ModifiedMDEFLocation]} "
                                                f"is not a valid location for {m_ModifiedMDEFLocation}")

            if assure(in_file, m_PerforceLocation):
                if assure(in_file[m_PerforceLocation], m_MDEFLocation) and len(in_file[m_PerforceLocation][m_MDEFLocation]) > 0:
                    if os.path.exists(getEnvVariableValue(P4_ROOT) + in_file[m_PerforceLocation][m_MDEFLocation]):
                        self.inMDEFLocation = in_file[m_PerforceLocation][m_MDEFLocation]
                    else:
                        raise FileNotFoundError(f"{in_file[m_PerforceLocation][m_MDEFLocation]} "
                                                f"is not a valid location for {m_MDEFLocation}")

            if assure(in_file, m_TestSuite):
                self.inRequiredTestSuites = dict()
                for test_suite in in_file[m_TestSuite]:
                    required_test_sets = dict()
                    for test_set, starting_id in in_file[m_TestSuite][test_suite].items():
                        if starting_id > 0 and not self.inFirstRevision:
                            required_test_sets[test_set] = starting_id
                        else:
                            required_test_sets[test_set] = 1
                    self.inRequiredTestSuites[test_suite] = required_test_sets

            if assure(in_file, m_ExternalArguments):
                self.inExternalArguments = dict()
                for test_suite, args_map in in_file[m_ExternalArguments].items():
                    if len(args_map) > 0:
                        self.inExternalArguments[test_suite] = args_map
        else:
            raise FileNotFoundError(f"{in_filepath} not found")

    def getConnectionString(self):
        return self.inConnectionString

    def getOlderMDEFRevision(self):
        return self.inOlderMDEFVersion if self.inOlderMDEFVersion > 0 else None

    def getNewerMDEFRevision(self):
        return self.inNewerMDEFVersion if self.inNewerMDEFVersion > 0 else None

    def getMDEFDifferenceFindMode(self):
        return self.inDifferenceFindMode

    def getMDEFLocation(self, in_perforce_loc: bool = False):
        if in_perforce_loc:
            return self.inMDEFLocation
        else:
            return getEnvVariableValue(P4_ROOT) + self.inMDEFLocation

    def getModifiedMDEFLocation(self):
        if self.getMDEFDifferenceFindMode() == m_ModifiedMDEFLocation:
            return self.inModifiedMDEFLocation
        else:
            return None

    def isFirstRevision(self):
        return self.inFirstRevision

    def getRequiredTestSuites(self):
        return self.inRequiredTestSuites

    def getExternalArguments(self):
        return self.inExternalArguments
