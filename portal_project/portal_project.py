# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

from osv import fields, osv
import pooler
import tools
from tools.config import config
from tools.translate import _
import netsvc

AVAILABLE_STATES = [
    ('draft','Draft'),
    ('open','Open'),
    ('cancel', 'Cancelled'),
    ('done', 'Closed'),
    ('pending','Pending')
]

def _project_get(self, cr, uid, context={}):
    obj = self.pool.get('project.project')
    ids = obj.search(cr, uid, [])
    res = obj.read(cr, uid, ids, ['id','name'], context)
    res = [(str(r['id']),r['name']) for r in res]
    return res

class users(osv.osv):
    _inherit = 'res.users'
    _columns = {
        'user_id' : fields.many2one('project.project', 'portal', ondelete='cascade'),
        'context_project_id': fields.selection(_project_get, 'Project',size=128),
        }
    _defaults = {
         'context_project_id' : lambda *args: '2',
            }

    def context_get(self, cr, uid, context=None):
        return super(users, self).context_get(cr, uid, context)

users()

class project_project(osv.osv):
    _inherit = "project.project"
    _description = "Project"

    def _get_details(self, cr, uid, ids_project, context={}, *arg):
        if not ids_project:
            return {}

        result = {}
        for id in ids_project:
            result[id] = {
                  'tasks': '',
                  'bugs': '',
                  'features': '',
                  'support_req': '',
                  'doc': ''
                          }
        ids = ",".join(map(str, ids_project))

        cr.execute('select count(t.id), p.id, p.name , sum(t.remaining_hours) as hours from project_project as p left join project_task as t on p.id=t.project_id \
                    where p.id in ('+ids+') and t.state=%s group by p.id, p.name', ('open',))
        for proj in cr.dictfetchall():
            result[proj['id']]['tasks'] = str(proj['count']) + ' opens, ' + str(proj['hours']) + ' remaining'

        cr.execute('select p.id, count(c.id), p.name from project_project as  p, crm_case as c where p.id=c.project_id and p.section_bug_id=c.section_id \
                    and p.id in ('+ids+') group by p.id,p.name')
        for bug in cr.dictfetchall():
            result[bug['id']]['bugs'] = str(bug['count']) + ' Total '
        cr.execute('select p.id, count(c.id),c.state,p.name from project_project as  p, crm_case as c where p.id=c.project_id and p.section_bug_id=c.section_id \
                    and p.id in ('+ids+') and c.state=%s group by p.id,p.name,c.state', ('open',))
        res_bug = cr.dictfetchall()
        for bug in res_bug:
            result[bug['id']]['bugs'] = result[bug['id']]['bugs'] + str(bug['count']) + ' open'

        cr.execute('select p.id, count(c.id), p.name from project_project as  p, crm_case as c where p.id=c.project_id and p.section_feature_id=c.section_id \
                    and p.id in ('+ids+') group by p.id,p.name')
        for feature in cr.dictfetchall():
            result[feature['id']]['features'] = str(feature['count']) + ' Total '
        cr.execute('select p.id, count(c.id),c.state,p.name from project_project as  p, crm_case as c where p.id=c.project_id and p.section_feature_id=c.section_id \
                    and p.id in ('+ids+') and c.state=%s group by p.id,p.name,c.state', ('open',))
        res_fet = cr.dictfetchall()
        for feature in res_fet:
            result[feature['id']]['features'] = result[feature['id']]['features'] + str(feature['count']) + ' open'

        cr.execute('select p.id, count(c.id), p.name from project_project as  p, crm_case as c where p.id=c.project_id and p.section_support_id=c.section_id \
                    and p.id in ('+ids+') group by p.id,p.name')
        for support in cr.dictfetchall():
            result[support['id']]['support_req'] = str(support['count']) + ' Total '
        cr.execute('select p.id, count(c.id),c.state,p.name from project_project as  p, crm_case as c where p.id=c.project_id and p.section_support_id=c.section_id \
                    and p.id in ('+ids+') and c.state=%s group by p.id,p.name,c.state', ('open',))
        res_sup = cr.dictfetchall()
        for support in res_sup:
            result[support['id']]['support_req'] = result[support['id']]['support_req'] + str(support['count']) + ' open'

        model = 'project.project'
        cr.execute('select count(i.id), p.id, p.name from project_project as p left join ir_attachment as i on i.res_id=p.id where p.id in ('+ids+') and i.res_model=%s group by p.id, p.name',(model,))
        for doc in cr.dictfetchall():
            result[doc['id']]['doc'] = str(doc['count'])
        cr.execute('select count(i.id), p.id, p.name, i.file_size as datas from project_project as p left join ir_attachment as i on i.res_id=p.id where p.id in ('+ids+') and i.res_model=%s group by p.id, p.name, i.file_size',(model,))
        dict_size = {}
        for id in ids_project:
            dict_size.setdefault(id, 0)
        for doc in cr.dictfetchall():
            dict_size[doc['id']] += doc['datas'] # To be test

        for s in dict_size:
            size = ''
            if dict_size[s] >= 1073741824:
                size = str((dict_size[s]) / 1024 / 1024 / 1024) + ' GB'
            elif dict_size[s] >= 1048576:
                size = str((dict_size[s]) / 1024 / 1024) + ' MB'
            elif dict_size[s] >= 1024:
                size = str((dict_size[s]) / 1024) + ' KB'
            elif dict_size[s] < 1024:
                size = str(dict_size[s]) + ' bytes'
            if result[s]['doc'] == '':
                result[s]['doc'] = '0'
            result[s]['doc'] = result[s]['doc'] + ' for ' +  size
        return result

    _columns = {
        'section_bug_id': fields.many2one('crm.case.section', 'Bug Section'),
        'section_feature_id': fields.many2one('crm.case.section', 'Feature Section'),
        'section_support_id': fields.many2one('crm.case.section', 'Support Section'),
        'section_annouce_id': fields.many2one('crm.case.section', 'Announce Section'),
        'tasks': fields.function(_get_details, type='char', size=64, method=True, string='Tasks', multi='project'),
        'bugs': fields.function(_get_details, type='char', size=64, method=True, string='Bugs', multi='project'),
        'features': fields.function(_get_details, type='char', size=64, method=True, string='Features',multi='project'),
        'support_req': fields.function(_get_details, type='char', size=64, method=True,multi='project', string='Support Requests'),
        'doc': fields.function(_get_details, type='char', method=True, size=64, multi='project', string='Documents'),
        'announce_ids': fields.one2many('crm.case', 'case_id', 'Announces'),
        'member_ids': fields.one2many('res.users', 'user_id', 'Project Members', help="Project's member. Not used in any computation, just for information purpose."),
        'bugs_ids':fields.one2many('report.crm.case.bugs', 'project_id', 'Bugs'),
        'hours_ids' : fields.one2many('report.project.working.hours', 'project_id', 'Working Hours'),
#        'hours_ids' : fields.function(_get_hours, type='float', method=True, store=True, string='Hours'),
        }

project_project()

class Wiki(osv.osv):
    _inherit = "wiki.wiki"
    _columns = {
        'project_id': fields.many2one('project.project', 'Project')
        }

Wiki()

class crm_case(osv.osv):
    _inherit = 'crm.case'
    _columns = {
        'project_id' : fields.many2one('project.project', 'Project', size=64),
        'bug_ids' : fields.one2many('crm.case', 'case_id', 'Latest Bugs'),
        'section_id' : fields.many2one('crm.case.section', 'Section', required=False)
    }

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
            context=None, count=False):
        if context is None:
            context = {}
        if 'section' in context and context['section']=='Bug Tracking':
            cr.execute('select c.id from crm_case c left join project_project p on p.id=c.project_id where c.section_id=p.section_bug_id')
            return map(lambda x: x[0], cr.fetchall())
        elif 'section' in context and context['section']=='Feature':
            cr.execute('select c.id from crm_case c left join project_project p on p.id=c.project_id where c.section_id=p.section_feature_id')
            return map(lambda x: x[0], cr.fetchall())
        elif 'section' in context and context['section']=='Support':
            cr.execute('select c.id from crm_case c left join project_project p on p.id=c.project_id where c.section_id=p.section_support_id')
            return map(lambda x: x[0], cr.fetchall())
        elif 'section' in context and context['section']=='Announce':
            cr.execute('select c.id from crm_case c left join project_project p on p.id=c.project_id where c.section_id=p.section_annouce_id')
            return map(lambda x: x[0], cr.fetchall())
        return super(crm_case, self).search(cr, uid, args, offset, limit, order, context, count)

    def create(self, cr, uid, values, *args, **kwargs):
        case_id = super(crm_case, self).create(cr, uid, values, *args, **kwargs)
        cr.commit()
        case = self.browse(cr, uid, case_id)
        if case.project_id:
            self.pool.get('project.project')._log_event(cr, uid, case.project_id.id, {
                                'res_id' : case.id,
                                'name' : case.name,
                                'description' : case.description,
                                'user_id': uid,
                                'action' : 'create',
                                'type'   : 'case'})
        return case_id

    def write(self, cr, uid, ids, vals, context={}):
        res = super(crm_case, self).write(cr, uid, ids, vals, context={})
        cr.commit()
        cases = self.browse(cr, uid, ids)
        for case in cases:
            if case.project_id:
                self.pool.get('project.project')._log_event(cr, uid, case.project_id.id, {
                                    'res_id' : case.id,
                                    'name' : case.name,
                                    'description' : case.description,
                                    'user_id': uid,
                                    'action' : 'write',
                                    'type' : 'case'})
        return res

crm_case()

class portal_account_analytic_planning(osv.osv):
    _inherit = 'report_account_analytic.planning'

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
            context=None, count=False):
        if context is None:
            context = {}
        if 'active_id' in context and context['active_id']:
            cr.execute("""select rp.id from report_account_analytic_planning rp \
                          where id in (select planning_id from project_task where project_id in (select id from project_project where id = %s))""" %(context['active_id']))
            return map(lambda x: x[0], cr.fetchall())
        return super(portal_account_analytic_planning, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)

portal_account_analytic_planning()

class report_project_working_hours(osv.osv):
    _name = "report.project.working.hours"
    _description = "Working hours of the day"
    _auto = False
    _columns = {
        'name': fields.date('Day', readonly=True),
        'user_id':fields.many2one('res.users', 'User', readonly=True),
        'hours': fields.float('Timesheet Hours'),
        'analytic_id' : fields.many2one('account.analytic.account', 'Analytic Account'),
        'description' : fields.text('Description'),
        'amount' : fields.float('Amount', required=True),
        'project_id' : fields.many2one('project.project', 'Project', size=64),
    }

    def init(self, cr):
        cr.execute("""
            create or replace view report_project_working_hours as (
                select
                    min(c.id) as id,
                    to_char(c.date, 'YYYY-MM-01') as name,
                    c.user_id as user_id,
                    c.unit_amount as hours,
                    c.amount as amount,
                    c.account_id as analytic_id,
                    c.name as description
                from
                    account_analytic_line c
                where
                    c.account_id in (select category_id from project_project where id = '2')
                group by c.user_id, c.date, c.unit_amount, c.account_id, c.amount, c.name
           )""")

report_project_working_hours()

class report_crm_case_bugs(osv.osv):
    _name = "report.crm.case.bugs"
    _description = "Bugs by State"
    _auto = False
    _rec_name = 'user_id'
    _columns = {
        'nbr': fields.integer('# of Cases', readonly=True),
        'state': fields.selection(AVAILABLE_STATES, 'Status', size=16, readonly=True),
        'user_id': fields.many2one('res.users', 'User', size=16, readonly=True),
        'project_id' : fields.many2one('project.project', 'Project', size=64),
        'section_id' : fields.many2one('crm.case.section', 'Section', required=False)
    }

    def init(self, cr):
        cr.execute("""
            create or replace view report_crm_case_bugs as (
                select
                    min(c.id) as id,
                    c.user_id,
                    c.project_id as project_id,
                    c.section_id as section_id,
                    count(*) as nbr,
                    c.state
                from
                    crm_case c left join project_project p on p.id = c.project_id
                where c.section_id = p.section_bug_id
                group by c.user_id, c.project_id, c.section_id, c.state
            )""")

report_crm_case_bugs()

class report_crm_case_features_user(osv.osv):
    _name = "report.crm.case.features.user"
    _description = "Features by User"
    _auto = False
    _rec_name = 'user_id'
    _columns = {
        'nbr': fields.integer('# of Cases', readonly=True),
        'user_id': fields.many2one('res.users', 'User', size=16, readonly=True),
    }
    def init(self, cr):
        cr.execute("""
            create or replace view report_crm_case_features_user as (
                select
                    min(c.id) as id,
                    c.user_id,
                    count(*) as nbr
                from
                    crm_case c left join project_project p on p.id = c.project_id
                where c.section_id = p.section_feature_id
                group by c.user_id, c.name
            )""")

report_crm_case_features_user()

class report_crm_case_support_user(osv.osv):
    _name = "report.crm.case.support.user"
    _description = "Support by User"
    _auto = False
    _rec_name = 'user_id'
    _columns = {
        'nbr': fields.integer('# of Cases', readonly=True),
        'user_id': fields.many2one('res.users', 'User', size=16, readonly=True),
    }
    def init(self, cr):
        cr.execute("""
            create or replace view report_crm_case_support_user as (
                select
                    min(c.id) as id,
                    c.user_id,
                    count(*) as nbr
                from
                    crm_case c left join project_project p on p.id = c.project_id
                where c.section_id = p.section_support_id
                group by c.user_id, c.name
            )""")

report_crm_case_support_user()

class report_crm_case_announce_user(osv.osv):
    _name = "report.crm.case.announce.user"
    _description = "Announces by User"
    _auto = False
    _rec_name = 'user_id'
    _columns = {
        'nbr': fields.integer('# of Cases', readonly=True),
        'user_id': fields.many2one('res.users', 'User', size=16, readonly=True),
    }
    def init(self, cr):
        cr.execute("""
            create or replace view report_crm_case_announce_user as (
                select
                    min(c.id) as id,
                    c.user_id,
                    count(*) as nbr
                from
                    crm_case c left join project_project p on p.id = c.project_id
                where c.section_id = p.section_annouce_id
                group by c.user_id, c.name
            )""")

report_crm_case_announce_user()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
