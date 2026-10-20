Build a streamlit application that facilitates  the following:

Two Routes:

- IVM Route # 1
    - Ingests AHK File
    - Ingests WIRE File
    - Ingests LSP File

- The IVM Route requires validation on the following:
    - BAG NUMBER
    - Receiving Warehouse Weight (kg)
    - RECEIVE DATE
    - OFFTAKER
    - LOT NUMBER

- Witnessing Route # 2
    - Ingests Warehouse File
    - Ingests WIRE File

- The witnessing route validate the following properties
    - BAG ID.
    - TRUCK REG
    - MINE SEAL
    - ZAMBIA WAREHOUSE GROSS WEIGHT (KG)
    - RECEIVED TRANSIT WAREHOUSE

Guidance on file content, applicable to both routes
- The bag ID "KxWx_xxxx_xxxx" is our primary key
- The output must specify which bags on one dataset but not the others


Gotchas, applicable to both routes:
- The WIRE file will always contain Bag ID's that exist in the system (correctly captured), the other two files may have mistyped Bag ID's

