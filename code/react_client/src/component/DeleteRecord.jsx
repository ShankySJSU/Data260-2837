import { useDispatch, useSelector } from "react-redux";
import { useNavigate, useParams } from "react-router-dom";

import {
    deleteInspection,
    clearError,
} from "../store/inspectionSlice";


export default function DeleteRecord() {
    const {
        id,
    } = useParams();

    const dispatch = useDispatch();
    const navigate = useNavigate();

    const {
        loading,
        error,
    } = useSelector((state) => state.inspections);


    const handleDelete = async () => {
        try {
            await dispatch(
                deleteInspection(Number(id))
            ).unwrap();

            navigate("/");
        } catch (errorMessage) {
            console.error(
                "Delete inspection failed:",
                errorMessage
            );
        }
    };


    return (
        <div>
            <h2>Delete Inspection Record</h2>

            <p>
                Are you sure you want to delete inspection ID {id}?
            </p>

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

            <button
                type="button"
                onClick={handleDelete}
                disabled={loading}
            >
                {loading ? "Deleting..." : "Delete"}
            </button>

            {" "}

            <button
                type="button"
                onClick={() => navigate("/")}
            >
                Cancel
            </button>
        </div>
    );
}