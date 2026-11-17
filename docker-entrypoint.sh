#!/bin/sh
# Hosting platforms (Render, Railway, Heroku...) give the database as
#   DATABASE_URL=postgresql://user:password@host:port/dbname
# Java's JDBC driver needs  jdbc:postgresql://host:port/dbname  with the user and password separate.
set -e

if [ -n "$DATABASE_URL" ] && [ -z "$DB_URL" ]; then
  without_scheme="${DATABASE_URL#*://}"      # user:password@host:port/dbname
  credentials="${without_scheme%%@*}"         # user:password
  location="${without_scheme#*@}"             # host:port/dbname
  export DB_URL="jdbc:postgresql://${location}"
  [ -z "$DB_USERNAME" ] && export DB_USERNAME="${credentials%%:*}"
  [ -z "$DB_PASSWORD" ] && export DB_PASSWORD="${credentials#*:}"
fi

exec java -jar app.jar
