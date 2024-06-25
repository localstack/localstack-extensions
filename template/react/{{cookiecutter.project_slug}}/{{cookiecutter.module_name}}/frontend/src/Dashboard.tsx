import { Button } from '@mui/material';
import React from 'react';
import { useNavigate } from 'react-router-dom';

export const Dashboard = () => {
  const navigate = useNavigate();

  return (
    <>
      Dashboard
      <Button onClick={() => navigate("/one")} variant='contained'>
        Page One
      </Button>
    </>
  );
}

