class safeMysql:

    def __init__(self, host, user, password, db):
      self.host=host
      self.user=user
      self.password=password
      self.db=db

    def connect(self):
      try:
          #connecting to mariadb
          self.conn = mariadb.connect(host=self.host, user=self.user, password=self.password, database=self.db)
          return True
      except mariadb._exceptions.OperationalError as e:
          return False
          
    def __getConn(self):
      return self.conn

    def execute_query(self, query_str, values=None):
        # defaults
        num_affected_rows = 0
        result_rows = None
        success = False
        message = "Error executing query: {}".format(query_str)
        # run the query
        try:
            mysql_conn = get_existing_mysql_connection()
            cur = mysql_conn.cursor()
            if values == None or len(values) < 1:
                num_affected_rows = cur.execute(query_str)
            else:
                num_affected_rows = cur.execute(query_str, values)
            result_rows = cur.fetchall()  # only relevant to select, but safe to run with others
            cur.close()
            mysql_conn.commit()
            success = True
            message = "Mysql success for query: {}".format(query_str)
        except BaseException as e:
            message = "Mysql error: {}; for query: {}".format(repr(e), query_str)
        return (success, num_affected_rows, result_rows, message)


    def execute_query_with_retry(self, query_str, values=None, num_tries=3, message=""):
        # defaults
        success = False
        num_affected_rows = 0
        result_rows = None
        this_message = "Error executing query: {}".format(query_str)
        # should we still try?
        if num_tries < 1:
            this_message = "Ran out of tries for query: {}".format(query_str)
            return (False, 0, None, message + '; ' + this_message)
        num_tries_after_this = num_tries - 1
        # try to execute query
        try:
            (success, num_affected_rows, result_rows,
            this_message) = execute_query(query_str, values)
        except BaseException as e:
            success = False
        # handle success or failure
        if success == True:
            return (True, num_affected_rows, result_rows, message + '; ' + this_message)
        else:
            connect()  # reconnect using password etc.
            return(execute_query_with_retry(query_str, values=values, num_tries=num_tries_after_this, message=(message + '; ' + this_message)))
