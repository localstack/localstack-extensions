import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  List,
  ListItem,
  ListItemText,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { ReactElement, useEffect, useMemo, useState } from "react";
import { AwsProxyApiClient } from "./utils";

const apiEndpoint = `${window.location.origin}/_localstack/aws`;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const Dashboard = (): ReactElement => {
  const [config, setConfig] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [isLoading, setLoading] = useState(false);
  const apiClient = useMemo(() => new AwsProxyApiClient(apiEndpoint), []);

  const saveConfig = async () => {
    setLoading(true);
    try {
      const envVars = {
        AWS_ACCESS_KEY_ID: accessKey,
        AWS_SECRET_ACCESS_KEY: secretKey,
        AWS_SESSION_TOKEN: sessionToken,
      };
      await apiClient.setConfig({ config, env_vars: envVars });
      await pollStatus("enabled");
    } finally {
      setLoading(false);
    }
  };
  const disableProxy = async () => {
    setLoading(true);
    try {
      await apiClient.disableProxy();
      await pollStatus("disabled");
      setAccessKey("");
      setSecretKey("");
      setSessionToken("");
    } finally {
      setLoading(false);
    }
  };
  const getStatus = async () => {
    const result = await apiClient.getStatus();
    setStatus(result.status);
    setConfig(result.config || "");
    return result;
  };

  const pollStatus = async (expected: string) => {
    await sleep(5000);
    for (var i = 0; i < 10; i++) {
      await sleep(3000);
      const result = await getStatus();
      if (result.status === expected) return;
    }
  };

  useEffect(() => {
    getStatus();
  }, [status]);

  return (
    <Card>
      <CardHeader
        title="AWS Cloud Proxy - LocalStack Extension"
        subheader="Mirror resources from real AWS accounts into your LocalStack instance, thereby 'bridging the gap' between local and remote cloud resources."
      />
      <CardContent>
        <Typography variant="body1" component="div" gutterBottom>
          Common Use Cases:
        </Typography>

        <List dense disablePadding>
          <ListItem>
            <ListItemText
              primary="Developing a local Lambda function that accesses a remote DynamoDB table."
              primaryTypographyProps={{ variant: "body2" }}
            />
          </ListItem>
          <ListItem>
            <ListItemText
              primary="Running a local Athena SQL query in LocalStack accessing files in a real S3 bucket in AWS."
              primaryTypographyProps={{ variant: "body2" }}
            />
          </ListItem>
          <ListItem>
            <ListItemText
              primary="Seeding a local Terraform script with SSM parameters from a real AWS account."
              primaryTypographyProps={{ variant: "body2" }}
            />
          </ListItem>
        </List>
        <TableContainer component={Box}>
          <Table>
            <TableBody>
              <TableRow
                sx={{ "&:last-child td, &:last-child th": { border: 0 } }}
              >
                <TableCell component="th" scope="row">
                  Proxy Status:
                </TableCell>
                <TableCell sx={{ width: "80%" }}>
                  <b>
                    {status === null
                      ? "loading ..."
                      : status === "enabled"
                      ? "enabled"
                      : "disabled"}
                  </b>
                  {status === "enabled" && (
                    <Button
                      sx={{ float: "right" }}
                      variant="contained"
                      onClick={disableProxy}
                      disabled={isLoading}
                    >
                      {isLoading ? "loading ..." : "Disable"}
                    </Button>
                  )}
                </TableCell>
              </TableRow>
              <TableRow
                sx={{
                  "&:last-child td, &:last-child th": { border: 0 },
                  py: 2,
                }}
              >
                <TableCell component="th" scope="row">
                  AWS Credentials:
                </TableCell>
                <TableCell sx={{ width: "80%", py: 2 }}>
                  <TextField
                    type="password"
                    value={accessKey}
                    onChange={(e) => setAccessKey(e.target.value)}
                    size="small"
                    style={{ width: "32%" }}
                    placeholder="AWS_ACCESS_KEY_ID"
                  />{" "}
                  <TextField
                    type="password"
                    value={secretKey}
                    onChange={(e) => setSecretKey(e.target.value)}
                    size="small"
                    style={{ width: "32%" }}
                    placeholder="AWS_SECRET_ACCESS_KEY"
                  />{" "}
                  <TextField
                    type="password"
                    value={sessionToken}
                    onChange={(e) => setSessionToken(e.target.value)}
                    size="small"
                    style={{ width: "32%" }}
                    placeholder="AWS_SESSION_TOKEN"
                  />
                  <Typography variant="subtitle2" sx={{ marginTop: 1 }}>
                    Please note: AWS credentials are only passed in-memory to
                    the LocalStack container and will <b>not</b> be persisted on
                    disk. For security reasons, please make sure to use scoped
                    credentials with the least set of required permissions
                    (ideally read-only).
                  </Typography>
                </TableCell>
              </TableRow>
              <TableRow
                sx={{
                  "&:last-child td, &:last-child th": { border: 0 },
                  py: 2,
                }}
              >
                <TableCell component="th" scope="row">
                  Proxy Configuration:
                </TableCell>
                <TableCell sx={{ width: "80%", py: 2 }}>
                  <TextField
                    value={config}
                    onChange={(e) => setConfig(e.target.value)}
                    multiline={true}
                    minRows={5}
                    size="small"
                    style={{ width: "100%" }}
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
      <CardActions>
        <Button
          onClick={saveConfig}
          variant="contained"
          color="primary"
          disabled={isLoading}
        >
          {isLoading ? "loading ..." : "Save configuration"}
        </Button>
      </CardActions>
    </Card>
  );
};
