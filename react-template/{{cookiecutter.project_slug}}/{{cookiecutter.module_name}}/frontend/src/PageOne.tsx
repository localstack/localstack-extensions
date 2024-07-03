import { Button, Card, CardContent, CardHeader, Typography } from '@mui/material';
import { ReactElement } from 'react';
import { useNavigate } from 'react-router-dom';

export const PageOne = (): ReactElement => {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader
        title={"Page One"}
        action={
          <Button
            onClick={() => navigate("/dashboard")}
            color="primary"
            variant="contained"
          >
            Dashboard
          </Button>
        }
      />
      <CardContent>
        <Typography>Lorem Ipsum</Typography>
      </CardContent>
    </Card>
  );
}

