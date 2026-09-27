import { BrowserRouter, Routes, Route } from "react-router-dom";

import Login from "./component/Login";
import Home from "./component/Home";
import CreateRecord from "./component/CreateRecord";
import UpdateRecord from "./component/UpdateRecord";
import DeleteRecord from "./component/DeleteRecord";

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