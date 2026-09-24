# METRICS.md – Homework 3
SID4: 2837  
Student: Shashank Ranjan  

# AI_USE.md - HW4

## 1. What I used an AI assistant for
I used an AI assistant to:
- help generate initial code templates for FastAPI + SQLAlchemy
- structure my React components
- write the RAG pipeline logic
- create benchmark scripts and packaging templates
I wrote all code manually into my project and tested each component myself.

## 2. One AI-produced output that was wrong
The assistant initially produced a JOIN example that used an outdated SQLAlchemy syntax not compatible with my installed version.

## 3. How I detected the problem
Running the backend produced this error:
"ArgumentError: Mapper option ... is not recognized"
I checked SQLAlchemy documentation (v2.x) and confirmed the syntax had changed.

## 4. What I changed and why it works now
I replaced the outdated JOIN syntax with:
options(joinedload(RestaurantInspection.related_items))

This syntax is correct for SQLAlchemy v2.x and results in the proper eager-loaded behavior.

This fixed the N+1 issue and produced valid results for both endpoints.

## Notes
- All files were generated specifically for HW4 based on restaurant domain requirements.

END OF FILE