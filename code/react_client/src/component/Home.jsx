import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";

import useAuth from "../hooks/useAuth";
import {
    fetchInspections,
    clearError,
} from "../store/inspectionSlice";


export default function Home() {
    const authenticated = useAuth();
    const navigate = useNavigate();
    const dispatch = useDispatch();

    const {
        records,
        loading,
        error,
    } = useSelector((state) => state.inspections);


    useEffect(() => {
        if (authenticated === false) {
            navigate("/login");
        }

        if (authenticated === true) {
            dispatch(fetchInspections());
        }
    }, [
        authenticated,
        dispatch,
        navigate,
    ]);


    if (authenticated === null) {
        return <p>Checking authentication...</p>;
    }


    if (loading) {
        return <p>Loading inspections...</p>;
    }


    return (
        <div>
            <h2>Restaurant Inspections</h2>

            <Link to="/create">
                Create New Inspection
            </Link>

            {error && (
                <div>
                    <p>{error}</p>

                    <button
                        onClick={() => dispatch(clearError())}
                    >
                        Dismiss
                    </button>
                </div>
            )}

            {!error && records.length === 0 && (
                <p>No inspections found.</p>
            )}

            <ul>
                {records.map((record) => (
                    <li key={record.id}>
                        <strong>{record.name}</strong>
                        {" | "}
                        Code: {record.inspection_code}
                        {" | "}
                        Status: {record.status}
                        {" | "}
                        Score: {record.score}
                        {" | "}
                        Restaurant ID: {record.restaurant_id}
                        {" "}

                        <Link to={`/update/${record.id}`}>
                            Update
                        </Link>

                        {" "}

                        <Link to={`/delete/${record.id}`}>
                            Delete
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
}