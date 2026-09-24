import { BrowserRouter, Routes, Route } from "react-router-dom";

import Login from "./components/Login";
import Home from "./components/Home";
import CreateRecord from "./components/CreateRecord";
import UpdateRecord from "./components/UpdateRecord";
import DeleteRecord from "./components/DeleteRecord";

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/login" element={<Login />} />
                <Route path="/create" element={<CreateRecord />} />
                <Route path="/update/:id" element={<UpdateRecord />} />
                <Route path="/delete/:id" element={<DeleteRecord />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;