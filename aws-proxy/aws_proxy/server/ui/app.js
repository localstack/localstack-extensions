const { useEffect, useState } = React;
const {
    ThemeProvider, CssBaseline, Button, TextField, Paper,
    Table, TableBody, TableCell, TableHead, TableRow, TableContainer
} = MaterialUI;

const apiEndpoint = `${window.location.origin}/_localstack/aws`;

const sleep = ms => new Promise(r => setTimeout(r, ms));

const sendRequest = async (path, request, method) => {
    const url = `${apiEndpoint}${path}`;
    method = method || (request ? "post": "get");
    request = typeof request !== "string" ? JSON.stringify(request) : request;
    const headers = request ? {"Content-Type": "application/json"} : {};
    const result = await axios[method](url, request, { headers });
    if (result.status >= 400) {
        throw Error(`Invalid API response (${result.status}): ${result.data}`);
    }
    return result.data;
};


const App = () => {
    const [config, setConfig] = useState('');
    const [status, setStatus] = useState(null);
    const [accessKey, setAccessKey] = useState('');
    const [secretKey, setSecretKey] = useState('');
    const [sessionToken, setSessionToken] = useState('');
    const [isLoading, setLoading] = useState(false);
    const isEnabled = status === "enabled";

    const saveConfig = async () => {
        setLoading(true);
        try {
            const envVars = {
                AWS_ACCESS_KEY_ID: accessKey,
                AWS_SECRET_ACCESS_KEY: secretKey,
                AWS_SESSION_TOKEN: sessionToken,
            };
            await sendRequest("/proxies", { config, env_vars: envVars });
            await pollStatus("enabled");
        } finally {
            setLoading(false);
        }
    };
    const disableProxy = async () => {
        setLoading(true);
        try {
            await sendRequest("/proxies/status", {status: "disabled"});
            await pollStatus("disabled");
            setAccessKey('');
            setSecretKey('');
            setSessionToken('');
        } finally {
            setLoading(false);
        }
    };
    const getStatus = async () => {
        const result = await sendRequest("/proxies/status");
        setStatus(result.status);
        setConfig(result.config || "");
        return result;
    };
    const pollStatus = async (expected) => {
        await sleep(5000);
        for(var i = 0; i < 10; i ++) {
            await sleep(3000);
            const result = await getStatus();
            if (result.status === expected) return;
        }
    };

    useEffect(() => {
        getStatus()
    }, [status]);

    return (<div>
      <h2>AWS Connection Proxy</h2>
      <div>
          <TableContainer component={Paper} sx={{ maxWidth: 800 }}>
            <Table>
              <TableBody>
                <TableRow sx={{'&:last-child td, &:last-child th': {border: 0}}}>
                  <TableCell component="th" scope="row">Proxy Status:</TableCell>
                  <TableCell sx={{width: "80%"}}>
                    <b>{status === null ? "loading ..." : status === "enabled" ? "enabled": "disabled"}</b>
                    {status === "enabled" && <Button sx={{float: "right"}} variant="contained"
                        onClick={disableProxy} disabled={isLoading}>{isLoading ? 'loading ...' : 'Disable'}</Button>}
                   </TableCell>
                </TableRow>
                <TableRow sx={{'&:last-child td, &:last-child th': {border: 0}}}>
                  <TableCell component="th" scope="row">AWS Credentials:</TableCell>
                  <TableCell sx={{ width: "80%" }}>
                        <TextField type="password" value={accessKey} onChange={(e) => setAccessKey(e.target.value)} size="small" style={{ width: "32%" }} placeholder="AWS_ACCESS_KEY_ID" /> {" "}
                        <TextField type="password" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} size="small" style={{ width: "32%" }} placeholder="AWS_SECRET_ACCESS_KEY" /> {" "}
                        <TextField type="password" value={sessionToken} onChange={(e) => setSessionToken(e.target.value)} size="small" style={{ width: "32%" }} placeholder="AWS_SESSION_TOKEN" />
                        Please note: AWS credentials are only passed in-memory to the LocalStack container and will <b>not</b> be persisted on disk. For security reasons, please make sure to use scoped credentials with the least set of required permissions (ideally read-only).
                    </TableCell>
                </TableRow>
                <TableRow sx={{'&:last-child td, &:last-child th': {border: 0}}}>
                  <TableCell component="th" scope="row">
                    Proxy Configuration:
                  </TableCell>
                  <TableCell sx={{width: "80%"}}>
                    <TextField value={config} onChange={(e) => setConfig(e.target.value)}
                        multiline={true} minRows={5} size="small" style={{width: "100%"}} />
                   </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        <Button onClick={saveConfig} variant="contained" disabled={isLoading}>{isLoading ? 'loading ...' : 'Save configuration'}</Button>
      </div>
    </div>);
}

const StyledApp = () => {
    return (
      <ThemeProvider theme={{}}>
        <CssBaseline />
        <App />
      </ThemeProvider>
    );
}

const container = document.getElementById('root');
const root = ReactDOM.createRoot(container);
root.render(React.createElement(StyledApp));