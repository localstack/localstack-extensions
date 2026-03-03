import { ReactElement } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Dashboard } from './components/Dashboard';

export const App = (): ReactElement => (
  <Routes>
    <Route path="/" element={<Navigate replace to="/dashboard" />} />
    <Route path="/dashboard" element={<Dashboard />} />
  </Routes>
);
