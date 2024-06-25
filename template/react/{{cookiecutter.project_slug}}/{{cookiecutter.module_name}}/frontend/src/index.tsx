import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { CustomRoutes } from './CustomRoutes';
import { BrowserRouter } from 'react-router-dom';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
const BASE_PATH = '/_localstack/{{cookiecutter.module_name}}';

root.render(
  <React.StrictMode>
    <BrowserRouter basename={BASE_PATH}>
      <CustomRoutes />
    </BrowserRouter >
  </React.StrictMode>
);

