# AI Use

1. I used an AI assistant to help map the HW6 requirements onto the existing HW5
   FastAPI and restaurant-inspection architecture, review the MongoDB schema design,
   and identify validation and testing cases.
2. I independently verified the route structure, database names, local model choice,
   and required configuration values against the assignment and my existing repository.
3. I detected problems by compiling the modified Python files, reviewing imports and
   route paths, and checking that the design keeps the HW5 SQL routes unchanged.
4. I changed the implementation to use separate MongoDB, schema, route, memory, and
   file-memory modules. This keeps responsibilities clear and allows the HW5 smoke
   tests to remain available while HW6 is added.
