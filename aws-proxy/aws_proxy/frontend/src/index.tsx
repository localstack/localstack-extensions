import ReactDOM from "react-dom";
import "./index.css";
import { CustomRoutes } from "./CustomRoutes";
import { HashRouter } from "react-router-dom";
import { LocalStackThemeProvider } from "@localstack/integrations";

ReactDOM.render(
  <LocalStackThemeProvider useExtensionLayout>
    <HashRouter>
      <CustomRoutes />
    </HashRouter>
  </LocalStackThemeProvider>,
  document.getElementById("root")
);
