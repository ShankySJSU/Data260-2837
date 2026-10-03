import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import api from "../api";

export const fetchInspections = createAsyncThunk(
    "inspections/fetchInspections",
    async (_, { rejectWithValue }) => {
        try {
            const response = await api.get("/inspection/", {
                params: {
                    page: 1,
                    page_size: 100,
                },
            });

            return response.data;
        } catch (error) {
            return rejectWithValue(
                error.response?.data?.detail ||
                "Unable to load inspections"
            );
        }
    }
);


export const fetchInspection = createAsyncThunk(
    "inspections/fetchInspection",
    async (id, { rejectWithValue }) => {
        try {
            const response = await api.get(`/inspection/${id}`);
            return response.data;
        } catch (error) {
            return rejectWithValue(
                error.response?.data?.detail ||
                "Unable to load inspection"
            );
        }
    }
);


export const createInspection = createAsyncThunk(
    "inspections/createInspection",
    async (inspection, { rejectWithValue }) => {
        try {
            const response = await api.post(
                "/inspection/",
                inspection
            );

            return response.data;
        } catch (error) {
            return rejectWithValue(
                error.response?.data?.detail ||
                "Unable to create inspection"
            );
        }
    }
);


export const updateInspection = createAsyncThunk(
    "inspections/updateInspection",
    async ({ id, data }, { rejectWithValue }) => {
        try {
            const response = await api.put(
                `/inspection/${id}`,
                data
            );

            return response.data;
        } catch (error) {
            return rejectWithValue(
                error.response?.data?.detail ||
                "Unable to update inspection"
            );
        }
    }
);


export const deleteInspection = createAsyncThunk(
    "inspections/deleteInspection",
    async (id, { rejectWithValue }) => {
        try {
            await api.delete(`/inspection/${id}`);
            return id;
        } catch (error) {
            return rejectWithValue(
                error.response?.data?.detail ||
                "Unable to delete inspection"
            );
        }
    }
);


const initialState = {
    records: [],
    selectedRecord: null,
    loading: false,
    error: null,
    success: null,
};


const inspectionSlice = createSlice({
    name: "inspections",
    initialState,
    reducers: {
        clearError: (state) => {
            state.error = null;
        },

        clearSuccess: (state) => {
            state.success = null;
        },

        clearSelectedRecord: (state) => {
            state.selectedRecord = null;
        },
    },

    extraReducers: (builder) => {
        builder

            // Fetch all inspections
            .addCase(fetchInspections.pending, (state) => {
                state.loading = true;
                state.error = null;
            })

            .addCase(fetchInspections.fulfilled, (state, action) => {
                state.loading = false;
                state.records = action.payload;
            })

            .addCase(fetchInspections.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })

            // Fetch one inspection
            .addCase(fetchInspection.pending, (state) => {
                state.loading = true;
                state.error = null;
                state.selectedRecord = null;
            })

            .addCase(fetchInspection.fulfilled, (state, action) => {
                state.loading = false;
                state.selectedRecord = action.payload;
            })

            .addCase(fetchInspection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })

            // Create inspection
            .addCase(createInspection.pending, (state) => {
                state.loading = true;
                state.error = null;
                state.success = null;
            })

            .addCase(createInspection.fulfilled, (state, action) => {
                state.loading = false;
                state.records.push(action.payload);
                state.success = "Inspection created successfully";
            })

            .addCase(createInspection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })

            // Update inspection
            .addCase(updateInspection.pending, (state) => {
                state.loading = true;
                state.error = null;
                state.success = null;
            })

            .addCase(updateInspection.fulfilled, (state, action) => {
                state.loading = false;

                const index = state.records.findIndex(
                    (record) => record.id === action.payload.id
                );

                if (index !== -1) {
                    state.records[index] = action.payload;
                }

                state.selectedRecord = action.payload;
                state.success = "Inspection updated successfully";
            })

            .addCase(updateInspection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })

            // Delete inspection
            .addCase(deleteInspection.pending, (state) => {
                state.loading = true;
                state.error = null;
                state.success = null;
            })

            .addCase(deleteInspection.fulfilled, (state, action) => {
                state.loading = false;

                state.records = state.records.filter(
                    (record) => record.id !== action.payload
                );

                state.success = "Inspection deleted successfully";
            })

            .addCase(deleteInspection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            });
    },
});


export const {
    clearError,
    clearSuccess,
    clearSelectedRecord,
} = inspectionSlice.actions;

export default inspectionSlice.reducer;