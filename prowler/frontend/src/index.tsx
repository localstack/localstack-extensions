import ReactDOM from 'react-dom';
import './index.css';
import { App } from './App';
import { HashRouter } from 'react-router-dom';
import { LocalStackThemeProvider } from '@localstack/integrations';

ReactDOM.render(
  <LocalStackThemeProvider useExtensionLayout>
    <HashRouter>
      <App />
    </HashRouter>
  </LocalStackThemeProvider>,
  document.getElementById('root'),
);
