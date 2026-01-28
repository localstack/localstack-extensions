{
  description = "localstack-extensions";

  inputs = {
    nixpkgs.url = "nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }@inputs:
    (
      let
        forAllSystems = nixpkgs.lib.genAttrs nixpkgs.lib.platforms.all;
      in
      {
        devShell = forAllSystems (system:
          let pkgs = import nixpkgs { inherit system; }; in
            pkgs.mkShell {
              buildInputs = with pkgs; [ uv python311 python311Packages.pip ty ];
            }
        );
      }
    );
}
