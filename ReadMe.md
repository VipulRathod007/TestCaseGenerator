# TestCases Generator
Generates Testcases and Result-sets of the newly added Tables and StoredProcedures.

## Requirements:
  1. [Python](https://www.python.org/downloads/)
  2. TouchStone
     1. Create a System environment variable `TOUCHSTONE_DIR` and set the directory path of the `Touchstone.exe`.
     2. Make sure to place following files in the Touchstone directory.
        1. Touchstone.exe
        2. sbicudt58_64.dll
        3. sbicuuc58d_64.dll
  3. ODBC Driver Setup

## Input:
 - Following are the required input parameters to generate the Test-cases and result-sets
 1. `ConnectionString` - Connection String to connect to the Data Source via ODBC Connector
 2. `DifferenceFindMode` - Mode to find the new added Tables & StoredProcedures
     1. `CompareTwoRevisions` - Comparing any two MDEF revisions
     2. `ModifiedMDEFLocation` - Compares Modified MDEF with the latest revision of the MDEF
     3. `IsFirstRevision` - Set to true if the MDEF is the first version else false
 3. `MDEFLocation` - Perforce Location of the MDEF
 4. `TestSuite` - TestSuite Configurations with the following format.
    - `{TestSuite-Name}`: {
      `{Testset-Name}`: `{Testset-Starting Id}`
      }     
 5. `ExternalArguments` - ExternalArguments for Test-suite `SP`

## Usage
- To generate Test-sets only but not result-sets
     ```bash
     python Runner.py -ts
     ```
- To generate Test-sets and result-sets both
     ```bash
     python Runner.py -rs
     ```
