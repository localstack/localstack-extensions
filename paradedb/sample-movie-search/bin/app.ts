#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { MovieSearchStack } from "../lib/movie-search-stack";

const app = new cdk.App();
new MovieSearchStack(app, "MovieSearchStack", {});
