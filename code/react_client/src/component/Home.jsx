/* List all records, update /delete button and create button */
import { useEffect, useState } from "react";
import api from "../api";
import useAuth from "../hooks/useAuth";
import { Link, useNavigate } from "react-router-dom";

export default function Home() {
    const authenticated = useAuth();
    const navigate = useNavigate();
    const [records, setRecords] = useState([]);

    useEffect(() => {
        if (authenticated === false) {
            navigate("/login");
        } else if (authenticated === true) {
            api.get("/inspection/")
               .then(res => setRecords(res.data))
               .catch(() => {});
        }
    }, [authenticated]);

    if (authenticated === null) return <p>Loading...</p>;

    return (
        <div>
            <h2>Restaurant Inspections</h2>

            <Link to="/create">Create New Record</Link>

            <ul>
                {records.map(r => (
                    <li key={r.id}>
                        {r.name} - {r.status}
                        {" "}
                        <Link to={`/update/${r.id}`}>Update</Link>
                        {" "}
                        <Link to={`/delete/${r.id}`}>Delete</Link>
                    </li>
                ))}
            </ul>
        </div>
    );
}