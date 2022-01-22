"""
General Utility Functions
"""

import os
import subprocess
from shutil import copy


m_DeleteFolder = '.ignore'


def assure(inParam: dict, inArg: str, ignoreError: bool = False):
    """Assure if the given `inArg` is a key of `inParam`"""
    if inParam is not None and inArg in inParam and inParam[inArg] is not None:
        return inParam[inArg]
    else:
        # If set to True, No Exception would be thrown but would return False
        # in case given inArg is not a key of inParam
        if ignoreError:
            return False
        else:
            raise KeyError(f"Invalid Expression: {inParam}[{inArg}]")


def getEnvVariableValue(inVarName: str):
    """Returns Environment Variable's Value from the given key"""
    return assure(dict(os.environ), inVarName)


def checkFilesInDir(inDirPath: str, inFiles: list):
    """
    Checks whether given files are present or not in the specified Directory \n
    :param inDirPath: The specified Directory path
    :param inFiles: List of files to check
    :return: Returns True if all the given files are present in the specified directory else False
    """
    if os.path.exists(inDirPath) and os.path.isdir(inDirPath):
        if inFiles is not None and len(inFiles) > 0 and all(map(lambda x: x in os.listdir(inDirPath), inFiles)):
            return True
    return False


def copyFilesInDir(inSrcDirPath: str, inDestDirPath: str, inFiles: list):
    """
    Copies given files in the specified Directory \n
    :param inSrcDirPath: The specified Source Directory path
    :param inDestDirPath: The specified Destination Directory path
    :param inFiles: List of files to copy
    :return: Return True if succeeded else False
    """
    if os.path.exists(inSrcDirPath) and os.path.isdir(inSrcDirPath) and os.path.exists(
            inDestDirPath) and os.path.isdir(inDestDirPath):
        try:
            [copy(os.path.join(inSrcDirPath, fileName), inDestDirPath) for fileName in inFiles]
            return True
        except FileNotFoundError as e:
            print('Error:', e)
            return False
    else:
        return False


class PerforceUtility:

    @staticmethod
    def getRevision(inFilePath: str, inFileRevision: int = None):
        """
        Gets a file from Perforce with the latest revision if revision not specified \n
        :param inFilePath: Path of the file to get revision
        :param inFileRevision: Revision Number of a file to get
        :return: Returns the Absolute Path of the File if downloaded successfully
        """
        if os.path.exists(inFilePath):
            inFileName = os.path.splitext(os.path.basename(os.path.abspath(inFilePath)))[0]
            inFileExtension = os.path.splitext(os.path.basename(os.path.abspath(inFilePath)))[1]
            outFileName = None
            if inFileRevision is not None:
                outFileName = f"{inFileName}_{inFileRevision}{inFileExtension}"
                subprocess.call(f"p4.exe print -o {os.path.join(m_DeleteFolder, outFileName)} "
                                f"{os.path.abspath(inFilePath)}#{inFileRevision}")
            else:
                outFileName = f"{inFileName}_Head{inFileExtension}"
                subprocess.call(f"p4.exe print -o {os.path.join(m_DeleteFolder, outFileName)} "
                                f"{os.path.abspath(inFilePath)}")
            return os.path.abspath(os.path.join(m_DeleteFolder, outFileName))
        else:
            raise FileNotFoundError(f"{inFilePath} is an invalid location")

    @staticmethod
    def getLatestRevisionNumber(inFilePath: str):
        """
        Finds the latest revision number of the file \n
        :param inFilePath: Path of the file to get latest revision number
        :return: Returns latest revision number of the specified file
        """
        if os.path.exists(inFilePath):
            output = subprocess.check_output(f"p4.exe files {os.path.abspath(inFilePath)}").decode().split(' - ')[0]
            fileName = os.path.basename(os.path.abspath(inFilePath))
            index = output.find(fileName + '#') + len(fileName) + 1
            return int(output[index:])
        else:
            raise FileNotFoundError(f"{inFilePath} is an invalid location")
