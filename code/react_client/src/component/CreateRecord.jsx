import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";

import {
    createInspection,
    clearError,
} from "../store/inspectionSlice";


export default function CreateRecord() {
    const dispatch = useDispatch();
    const navigate = useNavigate();

    const {
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
                createInspection(payload)
            ).unwrap();

            navigate("/");
        } catch (errorMessage) {
            console.error(
                "Create inspection failed:",
                errorMessage
            );
        }
    };


    return (
        <div>
            <h2>Create Inspection Record</h2>

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
                            placeholder="INSP-28370010"
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
                    {loading ? "Creating..." : "Create Inspection"}
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