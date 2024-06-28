import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import { CustomRoutes } from './CustomRoutes';
import { BrowserRouter } from 'react-router-dom';
import { LocalStackThemeProvider } from '@localstack/theme'

const BASE_PATH = '/_extension/{{cookiecutter.project_slug}}';

ReactDOM.render(
  <LocalStackThemeProvider useExtensionLayout>
    <BrowserRouter basename={BASE_PATH}>
      <CustomRoutes />
    </BrowserRouter >
  </LocalStackThemeProvider>,
  document.getElementById('root'),
);

