# SheetHero Backend V1

## Overview
``` mermaid

flowchart TD

U[user query and spreadsheets]
UND[understanding module]
EXE[execution module]
VAL[validation module]
OUT[output result and spreadsheets]

subgraph B[Sanbox]
    EXE
end


U --> UND

UND --> EXE

EXE --> VAL

VAL --> EXE

VAL --> OUT



```


