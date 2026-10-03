import { configureStore } from "@reduxjs/toolkit";
import inspectionReducer from "./inspectionSlice";

export const store = configureStore({
    reducer: {
        inspections: inspectionReducer,
    },
});