import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate, useParams } from "react-router-dom";

import {
    fetchInspection,
    updateInspection,
    clearError,
    clearSelectedRecord,
} from "../store/inspectionSlice";


export default function UpdateRecord() {
    const {
        id,
    } = useParams();

    const dispatch = useDispatch();
    const navigate = useNavigate();

    const {
        selectedRecord,
        loading,
        error,
    } = useSelector((state) => state.inspections);


    const [formData, setFormData] = useState({
        name: "",
        inspection_code: "",
        inspection_date: "",
        status: "PASS",
        score: 0,
        restaurant_id: 1,
    });


    useEffect(() => {
        dispatch(fetchInspection(id));

        return () => {
            dispatch(clearSelectedRecord());
        };
    }, [
        dispatch,
        id,
    ]);


    useEffect(() => {
        if (!selectedRecord) {
            return;
        }

        setFormData({
            name: selectedRecord.name || "",
            inspection_code: selectedRecord.inspection_code || "",
            inspection_date: selectedRecord.inspection_date
                ? selectedRecord.inspection_date.slice(0, 16)
                : "",
            status: selectedRecord.status || "PASS",
            score: selectedRecord.score ?? 0,
            restaurant_id: selectedRecord.restaurant_id || 1,
        });
    }, [selectedRecord]);


    const handleChange = (event) => {
        const {
            name,
            value,
        } = event.target;

        setFormData((previous) => ({
            ...previous,
            [name]: value,
        }));
    };


    const handleSubmit = async (event) => {
        event.preventDefault();

        const payload = {
            name: formData.name.trim(),
            inspection_code: formData.inspection_code
                .trim()
                .toUpperCase(),
            inspection_date: formData.inspection_date,
            status: formData.status.toUpperCase(),
            score: Number(formData.score),
            restaurant_id: Number(formData.restaurant_id),
        };

        try {
            await dispatch(
                updateInspection({
                    id: Number(id),
                    data: payload,
                })
            ).unwrap();

            navigate("/");
        } catch (errorMessage) {
            console.error(
                "Update inspection failed:",
                errorMessage
            );
        }
    };


    if (loading && !selectedRecord) {
        return <p>Loading inspection...</p>;
    }


    return (
        <div>
            <h2>Update Inspection Record</h2>

            {error && (
                <div>
                    <p>{error}</p>

                    <button
                        type="button"
                        onClick={() => dispatch(clearError())}
                    >
                        Dismiss Error
                    </button>
                </div>
            )}

            <form onSubmit={handleSubmit}>
                <div>
                    <label>
                        Restaurant Name:
                        <br />
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            required
                        />
                    </label>
                </div>

                <br />

                <div>
                    <label>
                        Inspection Code:
                        <br />
                        <input
                            type="text"
                            name="inspection_code"
                            value={formData.inspection_code}
                            onChange={handleChange}
                            required
                        />
                    </label>
                </div>

                <br />

                <div>
                    <label>
                        Inspection Date:
                        <br />
                        <input
                            type="datetime-local"
                            name="inspection_date"
                            value={formData.inspection_date}
                            onChange={handleChange}
                            required
                        />
                    </label>
                </div>

                <br />

                <div>
                    <label>
                        Status:
                        <br />
                        <select
                            name="status"
                            value={formData.status}
                            onChange={handleChange}
                        >
                            <option value="PASS">PASS</option>
                            <option value="FAIL">FAIL</option>
                            <option value="WARNING">
                                WARNING
                            </option>
                        </select>
                    </label>
                </div>

                <br />

                <div>
                    <label>
                        Score:
                        <br />
                        <input
                            type="number"
                            name="score"
                            min="0"
                            max="100"
                            value={formData.score}
                            onChange={handleChange}
                            required
                        />
                    </label>
                </div>

                <br />

                <div>
                    <label>
                        Restaurant ID:
                        <br />
                        <input
                            type="number"
                            name="restaurant_id"
                            min="1"
                            value={formData.restaurant_id}
                            onChange={handleChange}
                            required
                        />
                    </label>
                </div>

                <br />

                <button
                    type="submit"
                    disabled={loading}
                >
                    {loading ? "Updating..." : "Update Inspection"}
                </button>
            </form>

            <br />

            <button
                type="button"
                onClick={() => navigate("/")}
            >
                Cancel
            </button>
        </div>
    );
}