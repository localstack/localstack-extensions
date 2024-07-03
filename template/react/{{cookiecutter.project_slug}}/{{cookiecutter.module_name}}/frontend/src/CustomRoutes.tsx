import { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { PageOne } from "./PageOne";
import { Dashboard } from "./Dashboard";

export const CustomRoutes = (): ReactElement => (
  <Routes>
    {/* Make sure to always have a route fallback to "/" as it is the default page that gets opened from the web app*/}
    <Route path="/" element={<Navigate replace to="/dashboard" />} /> 
    <Route element={<Dashboard />} path="/dashboard" />
    <Route element={<PageOne />} path="/one" />
  </Routes>
)