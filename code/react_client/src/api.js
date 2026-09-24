import axios from "axios";

const api = axios.create({
    baseURL: "http://localhost:8137",
    withCredentials: true   // IMPORTANT: send cookie
});

export default api;