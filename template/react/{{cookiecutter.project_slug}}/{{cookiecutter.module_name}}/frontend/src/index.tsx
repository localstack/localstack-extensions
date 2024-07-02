import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import { CustomRoutes } from './CustomRoutes';
import { BrowserRouter } from 'react-router-dom';
import { LocalStackThemeProvider } from '@localstack/theme'

const EXTENSION_NAME = '{{cookiecutter.project_slug}}';

const getBaseName = () => {
  if (!window.location.origin.includes(EXTENSION_NAME)) {
    return `/_extension/${EXTENSION_NAME}`;
  }
  return '';
};


ReactDOM.render(
  <LocalStackThemeProvider useExtensionLayout>
    <BrowserRouter basename={getBaseName()}>
      <CustomRoutes />
    </BrowserRouter >
  </LocalStackThemeProvider>,
  document.getElementById('root'),
);

