import { Button } from "@mui/material";
import { ReactElement } from "react";
import { useNavigate } from "react-router-dom";

export const PageOne = (): ReactElement => {
  const navigate = useNavigate();

  return (
    <>
      Page One
      <Button onClick={() => navigate("/")} variant='contained'>
        Dashboard
      </Button>
    </>
  );
}