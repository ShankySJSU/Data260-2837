import api from "../api";
import { useParams, useNavigate } from "react-router-dom";

export default function DeleteRecord() {
    const { id } = useParams();
    const navigate = useNavigate();

    const handleDelete = async () => {
        await api.delete(`/inspection/${id}`);
        navigate("/");
    };

    return (
        <div>
            <h2>Delete Record</h2>
            <p>Are you sure you want to delete this record?</p>
            <button onClick={handleDelete}>Delete</button>
        </div>
    );
}