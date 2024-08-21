import { Button, Card, CardContent, CardHeader, Typography } from '@mui/material';
import { ReactElement } from 'react';
import { useNavigate } from 'react-router-dom';

export const Dashboard = (): ReactElement => {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader
        title={"Dashboard"}
        action={
          <Button
            onClick={() => navigate("/one")}
            color="primary"
            variant="contained"
          >
            Page One
          </Button>
        }
      />
      <CardContent>
        <Typography>Lorem Ipsum</Typography>
      </CardContent>
    </Card>
  );
}

