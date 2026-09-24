import { useState } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";

export default function CreateRecord() {
    const [name, setName] = useState("");
    const [status, setStatus] = useState("");
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        await api.post("/inspection/", {
            name,
            status
        });
        navigate("/");
    };

    return (
        <div>
            <h2>Create Inspection Record</h2>

            <form onSubmit={handleSubmit}>
                <input
                    type="text"
                    placeholder="Restaurant Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                /><br/>

                <input
                    type="text"
                    placeholder="Status"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                /><br/>

                <button>Create</button>
            </form>
        </div>
    );
}