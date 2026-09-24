import { useState, useEffect } from "react";
import api from "../api";
import { useParams, useNavigate } from "react-router-dom";

export default function UpdateRecord() {
    const { id } = useParams();
    const navigate = useNavigate();

    const [name, setName] = useState("");
    const [status, setStatus] = useState("");

    useEffect(() => {
        api.get(`/inspection/${id}`)
           .then(res => {
               setName(res.data.name);
               setStatus(res.data.status);
           });
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        await api.put(`/inspection/${id}`, {
            name,
            status
        });
        navigate("/");
    };

    return (
        <div>
            <h2>Update Record</h2>

            <form onSubmit={handleSubmit}>
                <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                /><br/>

                <input
                    type="text"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                /><br/>

                <button>Update</button>
            </form>
        </div>
    );
}