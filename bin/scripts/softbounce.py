#!/usr/bin/env python
#	-*- mode: python; mode: fold -*-
"""**********************************************************************************
* The contents of this file are subject to the Common Public Attribution
* License Version 1.0 (the "License"); you may not use this file except in
* compliance with the License. You may obtain a copy of the License at
* http://www.openemm.org/cpal1.html. The License is based on the Mozilla
* Public License Version 1.1 but Sections 14 and 15 have been added to cover
* use of software over a computer network and provide for limited attribution
* for the Original Developer. In addition, Exhibit A has been modified to be
* consistent with Exhibit B.
* Software distributed under the License is distributed on an "AS IS" basis,
* WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
* the specific language governing rights and limitations under the License.
* 
* The Original Code is OpenEMM.
* The Original Developer is the Initial Developer.
* The Initial Developer of the Original Code is AGNITAS AG. All portions of
* the code written by AGNITAS AG are Copyright (c) 2007 AGNITAS AG. All Rights
* Reserved.
* 
* Contributor(s): AGNITAS AG. 
**********************************************************************************
"""
#
import	sys, getopt
import	time, datetime
import	agn
agn.require ('2.9.9')
agn.loglevel = agn.LV_INFO

exts = lambda a: a != 1 and 's' or ''
exty = lambda a: a != 1 and 'ies' or 'y'

class Softbounce (object):
	bounceCollectTable = 'bounce_collect_tbl'
	timestampID = 2
	def __init__ (self, db, curs): #{{{
		self.db = db
		self.curs = curs
		self.timestamp = None
		self.ok = True
	#}}}
	def done (self): #{{{
		agn.log (agn.LV_INFO, 'done', 'Cleanup starting')
		self.finalizeTimestamp ()
		agn.log (agn.LV_INFO, 'done', 'Cleanup done')
	#}}}
	def setup (self): #{{{
		rc = True
		agn.log (agn.LV_INFO, 'setup', 'Setup starting')
		agn.log (agn.LV_INFO, 'setup', 'Setup done')
		return rc
	#}}}
	def __do (self, query, data, what, cursor = None): #{{{
		try:
			if cursor is None:
				cursor = self.curs
			agn.log (agn.LV_INFO, 'do', what)
			rows = cursor.update (query, data, commit = True)
			agn.log (agn.LV_INFO, 'do', '%s: affected %d row%s' % (what, rows, exts (rows)))
		except agn.error, e:
			agn.log (agn.LV_ERROR, 'do', '%s: failed using query %s %r: %s (%s)' % (what, query, data, e.msg, self.db.lastError ()))
	#}}}
	def removeOldEntries (self): #{{{
		agn.log (agn.LV_INFO, 'expire', 'Remove old entries from softbounce_email_tbl')

		old = time.localtime (time.time () - 180 * 24 * 60 * 60)
		query = 'DELETE FROM softbounce_email_tbl WHERE creation_date <= :expire AND company_id'
		data = {'expire': datetime.datetime (old.tm_year, old.tm_mon, old.tm_mday)}
		self.__do (query, data, 'Remove old addresses from softbounce_email_tbl')
		agn.log (agn.LV_INFO, 'expire', 'Removing of old entries from softbounce_email_tbl done')
	#}}}
	def setupTimestamp (self): #{{{
		agn.log (agn.LV_INFO, 'timestamp', 'Setup timestamp')
		self.timestamp = agn.Timestamp (self.timestampID)
		self.timestamp.setup (self.db)
		time.sleep (1)
		agn.log (agn.LV_INFO, 'timestamp', 'Setup done')
	#}}}
	def collectNewBounces (self): #{{{
		agn.log (agn.LV_INFO, 'collect', 'Start collecting new bounces')

		iquery = 'INSERT INTO bounce_collect_tbl (customer_id, company_id, mailing_id, change_date) VALUES (:customer, :company, :mailing, current_timestamp)'
		insert = self.db.cursor ()
		if insert is None:
			raise agn.error ('collectNewBounces: Failed to get new cursor for insertion')
		bquery = self.db.cursor ()
		if bquery is None:
			raise agn.error ('collectNewBounces: Failed to get new cursor for bounce query')
		data = {}
		query =  'SELECT customer_id, company_id, mailing_id, detail FROM bounce_tbl WHERE %s ORDER BY company_id, customer_id' % self.timestamp.makeBetweenClause ('change_date', data)
		cur = [0, 0, 0, 0]
		(records, uniques, inserts) = (0, 0, 0)
		if bquery.query (query, data) is None:
			raise agn.error ('collectNewBounces: Failed to query bounce_tbl using: %s' % query)
		while cur is not None:
			try:
				record = bquery.next ()
				records += 1
			except StopIteration:
				record = None
			if record is None or cur[0] != record[0] or cur[1] != record[1]:
				if record is not None:
					uniques += 1
				if cur[0] > 0 and cur[3] >= 400 and cur[3] < 510:
					parm = {
						'customer': cur[0],
						'company': cur[1],
						'mailing': cur[2]
					}
					insert.update (iquery, parm)
					inserts += 1
					if inserts % 10000 == 0 or record is None:
						agn.log (agn.LV_DEBUG, 'collect', 'Inserted now %s record%s' % (agn.numfmt (inserts), exts (inserts)))
						insert.sync ()
				cur = record
			elif record[3] > cur[3]:
				cur = list (record)
		self.db.commit ()
		bquery.close ()
		insert.close ()
		agn.log (agn.LV_INFO, 'collect', 'Read %d records (%d uniques) and inserted %d' % (records, uniques, inserts))
	#}}}
	def finalizeTimestamp (self): #{{{
		agn.log (agn.LV_INFO, 'timestamp', 'Finalizing timestamp')
		if self.timestamp:
			self.timestamp.done (self.ok)
			self.timestamp = None
		agn.log (agn.LV_INFO, 'timestamp', 'Timestamp finalized')
	#}}}
	def mergeNewBounces (self): #{{{
		agn.log (agn.LV_INFO, 'merge', 'Start merging new bounces into softbounce_email_tbl')

		iquery = 'INSERT INTO softbounce_email_tbl (company_id, email, bnccnt, mailing_id, creation_date, change_date) VALUES (:company, :email, 1, :mailing, now(), now())'
		uquery = 'UPDATE softbounce_email_tbl SET mailing_id = :mailing, change_date = now(), bnccnt=bnccnt+1 WHERE company_id = :company AND email = :email'
		icurs = self.db.cursor ()
		ucurs = self.db.cursor ()
		squery = 'SELECT count(*) FROM softbounce_email_tbl WHERE company_id = :company AND email = :email'
		scurs = self.db.cursor ()
		dquery = 'DELETE FROM bounce_collect_tbl WHERE company_id = :company'
		dcurs = self.db.cursor ()
		if None in [ icurs, ucurs, scurs, dcurs ]:
			raise agn.error ('mergeNewBounces: Unable to setup curses for merging')

		coll = [1]
		for company in sorted (coll):
			agn.log (agn.LV_INFO, 'merge', 'Working on %d' % company)
			query =  'SELECT mt.customer_id, mt.mailing_id, cust.email '
			query += 'FROM bounce_collect_tbl mt, customer_%d_tbl cust ' % company
			query += 'WHERE cust.customer_id = mt.customer_id '
			query += 'AND mt.company_id = %d ' % company
			query += 'ORDER BY cust.email, mt.mailing_id'

			for record in self.curs.query (query):
				(cuid, mid, eml) = record
				parm = {
					'company': company,
					'customer': cuid,
					'mailing': mid,
					'email': eml
				}
				data = scurs.querys (squery, parm, cleanup = True)
				if not data is None:
					if data[0] == 0:
						icurs.update (iquery, parm, cleanup = True)
					else:
						ucurs.update (uquery, parm, cleanup = True)
			parm = {
				'company': company
			}
			dcurs.update (dquery, parm, cleanup = True)
			self.db.commit ()
		icurs.close ()
		ucurs.close ()
		scurs.close ()
		dcurs.close ()
		agn.log (agn.LV_INFO, 'merge', 'Merging of new bounces done')
	#}}}
	def convertToHardbounce (self): #{{{
		agn.log (agn.LV_INFO, 'conv', 'Start converting softbounces to hardbounce')

		coll = [1]
		stats = []
		for company in sorted (coll):
			cstat = [company, 0, 0]
			stats.append (cstat)
			agn.log (agn.LV_INFO, 'conv', 'Working on %d' % company)
			dquery = 'DELETE FROM softbounce_email_tbl WHERE company_id = %d AND email = :email' % company
			dcurs = self.db.cursor ()
			uquery = self.curs.rselect ('UPDATE customer_%d_binding_tbl SET user_status = 2, user_remark = \'Softbounce\', exit_mailing_id = :mailing, change_date = %%(sysdate)s WHERE customer_id = :customer AND user_status = 1' % company)
			bquery = self.curs.rselect ('INSERT INTO bounce_tbl (company_id, customer_id, detail, mailing_id, change_date, dsn) VALUES (%d, :customer, 510, :mailing, %%(sysdate)s, 599)' % company)
			ucurs = self.db.cursor ()

			squery =  'SELECT email, mailing_id, bnccnt, creation_date, change_date FROM softbounce_email_tbl WHERE company_id = %d AND bnccnt > 7 AND DATEDIFF(change_date,creation_date) > 30' % company
			scurs = self.db.cursor ()
			if None in [dcurs, ucurs, scurs]:
				raise agn.error ('Failed to setup curses')

			lastClick = 30
			lastOpen = 30
			def toDatetime (offset):
				tm = time.localtime (time.time () -offset * 24 * 60 * 60)
				return datetime.datetime (tm.tm_year, tm.tm_mon, tm.tm_mday)
			lastClickTS = toDatetime (lastClick)
			lastOpenTS = toDatetime (lastOpen)
			ccount = 0
			for record in scurs.query (squery):
				parm = {
					'email': record[0],
					'mailing': record[1],
					'bouncecount': record[2],
					'creationdate': record[3],
					'timestamp': record[4],
					'customer': None
				}
				query =  'SELECT customer_id FROM customer_%d_tbl WHERE email = :email ' % company
				data = self.curs.querys (query, parm, cleanup = True)
				if data is None:
					continue
				custs = [agn.struct (id = _d, click = 0, open = 0) for _d in data if _d]
				if not custs:
					continue
				if len (custs) == 1:
					cclause = 'customer_id = %d' % custs[0].id
				else:
					cclause = 'customer_id IN (%s)' % ', '.join ([str (_c.id) for _c in custs])

				parm['ts'] = lastClickTS
				query =  'SELECT customer_id, count(*) FROM rdir_log_tbl WHERE %s AND company_id = %d' % (cclause, company)
				query += ' AND change_date > :ts GROUP BY customer_id'
				for r in self.curs.queryc (query, parm, cleanup = True):
					for c in custs:
						if c.id == r[0]:
							c.click += r[1]
				parm['ts'] = lastOpenTS
				query =  'SELECT customer_id, count(*) FROM onepixel_log_tbl WHERE %s AND company_id = %d' % (cclause, company)
				query += ' AND change_date > :ts GROUP BY customer_id'
				for r in self.curs.queryc (query, parm, cleanup = True):
					for c in custs:
						if c.id == r[0]:
							c.open += r[1]
				for c in custs:
					if c.click > 0 or c.open > 0:
						cstat[1] += 1
						agn.log (agn.LV_INFO, 'conv', 'Email %s [%d] has %d klick(s) and %d onepix(es) -> active' % (parm['email'], c.id, c.click, c.open))
					else:
						cstat[2] += 1
						agn.log (agn.LV_INFO, 'conv', 'Email %s [%d] has no klicks and no onepixes -> hardbounce' % (parm['email'], c.id))
						parm['customer'] = c.id
						ucurs.update (uquery, parm, cleanup = True)
						ucurs.execute (bquery, parm, cleanup = True)
				dcurs.update (dquery, parm, cleanup = True)
				ccount += 1
				if ccount % 1000 == 0:
					agn.log (agn.LV_INFO, 'conv', 'Commiting at %s' % agn.numfmt (ccount))
					self.db.commit ()
			self.db.commit ()
			scurs.close ()
			ucurs.close ()
			dcurs.close ()
		for cstat in stats:
			agn.log (agn.LV_INFO, 'conv', 'Company %d has %d active and %d marked as hardbounced users' % tuple (cstat))
		agn.log (agn.LV_INFO, 'conv', 'Converting softbounces to hardbounce done')
	#}}}
#
def main ():
	rc = 1
	(opts, param) = getopt.getopt (sys.argv[1:], 'v')
	for opt in opts:
		if opt[0] == '-v':
			agn.outlevel = agn.LV_DEBUG
			agn.outstream = sys.stdout
	agn.lock ()
	agn.log (agn.LV_INFO, 'main', 'Starting up')
	db = agn.DBaseID ()
	if db is not None:
#		db.log = lambda a: agn.log (agn.LV_DEBUG, 'db', a)
		curs = db.cursor ()
		if curs is not None:
			softbounce = Softbounce (db, curs)
			if softbounce.setup ():
				try:
					softbounce.removeOldEntries ()
					softbounce.setupTimestamp ()
					softbounce.collectNewBounces ()
					softbounce.finalizeTimestamp ()
					softbounce.mergeNewBounces ()
					softbounce.convertToHardbounce ()
					rc = 0
				except agn.error, e:
					agn.log (agn.LV_ERROR, 'main', 'Failed due to %s' % e.msg)
					softbounce.ok = False
				softbounce.done ()
			else:
				agn.log (agn.LV_ERROR, 'main', 'Setup of handling failed')
			curs.sync ()
			curs.close ()
		else:
			agn.log (agn.LV_ERROR, 'main', 'Failed to get database cursor')
		db.close ()
	else:
		agn.log (agn.LV_ERROR, 'main', 'Failed to setup database interface')
	agn.log (agn.LV_INFO, 'main', 'Going down')
	agn.unlock ()
	if rc:
		sys.exit (rc)

if __name__ == '__main__':
	main ()
