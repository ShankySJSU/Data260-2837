import { useEffect, useState } from "react";
import api from "../api";

export default function useAuth() {
    const [authenticated, setAuthenticated] = useState(null);

    useEffect(() => {
        api.get("/me")
           .then(() => setAuthenticated(true))
           .catch(() => setAuthenticated(false));
    }, []);

    return authenticated;
}