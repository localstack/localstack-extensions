import ReactDOM from 'react-dom';
import './index.css';
import { CustomRoutes } from './CustomRoutes';
import { BrowserRouter } from 'react-router-dom';
import { LocalStackThemeProvider } from '@localstack/integrations'
import { DEVELOPMENT_ENVIRONMENT } from './constants';

const EXTENSION_NAME = '{{cookiecutter.project_slug}}'

const getBaseName = () => {
  if (window.location.origin.includes(EXTENSION_NAME) || DEVELOPMENT_ENVIRONMENT) {
    return '';
  }

  return `/_extension/${EXTENSION_NAME}`;
};

ReactDOM.render(
  <LocalStackThemeProvider useExtensionLayout>
    <BrowserRouter basename={getBaseName()}>
      <CustomRoutes />
    </BrowserRouter >
  </LocalStackThemeProvider>,
  document.getElementById('root'),
);
