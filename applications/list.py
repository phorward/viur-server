# -*- coding: utf-8 -*-
from server.bones import baseBone
from server.skeleton import Skeleton
from server.skellist import Skellist
from server import utils, session,  errors, conf
from google.appengine.api import users
import logging

class List( object ):
	adminInfo = {	"name": "BaseApplication", #Name of this modul, as shown in Apex (will be translated at runtime)
				"handler": "list",  #Which handler to invoke
				"icon": "", #Icon for this modul
				}

	def __init__( self, modulName, modulPath, *args, **kwargs ):
		super( List, self ).__init__( *args, **kwargs )
		self.modulName = modulName
		self.modulPath = modulPath
		if self.adminInfo:
			rights = ["add", "edit", "view", "delete"]
			for r in rights:
				rightName = "%s-%s" % ( modulName, r )
				if not rightName in conf["viur.accessRights"]:
					conf["viur.accessRights"].append( rightName )

	def preview( self, skey, *args, **kwargs ):
		"""
			Renders the viewTemplate with the values given.
			This allows to preview an entry without having to save it first
		"""
		if not self.canPreview( ):
			raise errors.Unauthorized()
		if not utils.validateSecurityKey( skey ):
			raise errors.PreconditionFailed()
		skel = self.viewSkel()
		skel.fromClient( kwargs )
		return( self.render.view( skel ) )
	preview.exposed = True
	
	def view( self, *args, **kwargs ):
		"""
			Prepares and renders a single entry for viewing
		"""
		if "id" in kwargs:
			id = kwargs["id"]
		elif( len( args ) >= 1 ):
			id= args[0]
		else:
			raise errors.NotAcceptable()
		skel = self.viewSkel()
		if "canView" in dir( self ):
			if not self.canView( id ):
				raise errors.Unauthorized()
			if not skel.fromDB( id ):
				raise errors.NotFound()
		else:
			queryObj = utils.buildDBFilter( skel, {"id": id} )
			queryObj = self.listFilter( queryObj ) #Access control
			if not queryObj:
				raise errors.Unauthorized()
			if not skel.fromDB( queryObj ):
				raise errors.NotFound()
		return( self.render.view( skel ) )
	view.exposed = True
	
	def list( self, *args, **kwargs ):
		"""
			Renders a list of entries.
			All supplied parameters are interpreted as filters for the elements displayed
			Unlike Tree, Hierarchy or Singleton, access control in this function is realized
			by calling the function listFilter, which updates the query-filter to contain only
			elements which the user is allowed to view.
		"""
		mylist = Skellist( self.viewSkel )
		queryObj = utils.buildDBFilter( self.viewSkel(), kwargs ) #Build the initial one
		queryObj = self.listFilter( queryObj ) #Access control
		if not queryObj:
			raise( errors.Unauthorized() )
		mylist.fromDB( queryObj )
		return( self.render.list( mylist ) )
	list.exposed = True

	def edit( self, *args, **kwargs ):
		"""
			Edit the entry with the given id
		"""
		if "skey" in kwargs:
			skey = kwargs["skey"]
		else:
			skey = ""
		if( len( args ) == 1 ):
			id= args[0]
		elif "id" in kwargs:
			id = kwargs["id"]
		else:
			raise errors.NotAcceptable()
		skel = self.editSkel()
		if id == "0":
			return( self.render.edit( skel ) )
		if not self.canEdit( id ):
			raise errors.Unauthorized()
		if not skel.fromDB( id ):
			raise errors.NotAcceptable()
		if len(kwargs)==0 or skey=="" or not skel.fromClient( kwargs ) or ("bounce" in list(kwargs.keys()) and kwargs["bounce"]=="1"):
			return( self.render.edit( skel ) )
		if not utils.validateSecurityKey( skey ):
			raise errors.PreconditionFailed()
		skel.toDB( id )
		self.onItemEdited( id, skel )
		return self.render.editItemSuccess( skel )
	edit.exposed = True
	edit.forceSSL = True
	
	def add( self, *args, **kwargs ):
		"""
			Add a new entry.
		"""
		if "skey" in kwargs:
			skey = kwargs["skey"]
		else:
			skey = ""
		if not self.canAdd( ):
			raise errors.Unauthorized()
		skel = self.addSkel()
		if not skel.fromClient( kwargs ) or len(kwargs)==0 or skey=="" or ("bounce" in list(kwargs.keys()) and kwargs["bounce"]=="1"):
			return( self.render.add( skel ) )
		if not utils.validateSecurityKey( skey ):
			raise errors.PreconditionFailed()
		id = skel.toDB( )
		self.onItemAdded( id, skel )
		return self.render.addItemSuccess( id, skel )
	add.exposed = True
	add.forceSSL = True
	
	def delete( self, id, skey, *args, **kwargs ):
		"""
			Delete an entry.
		"""
		if not self.canDelete( id ):
			raise errors.Unauthorized()
		skel = self.editSkel()
		if not skel.fromDB( id ):
			raise errors.NotFound()
		if not utils.validateSecurityKey( skey ):
			raise errors.PreconditionFailed()
		skel.delete( id )
		self.onItemDeleted( id, skel )
		return self.render.deleteSuccess( skel )
	delete.exposed = True
	delete.forceSSL = True

	def listFilter( self, filter ):
		"""
			Changes the db-filter, sothat the result will only include entries the user is allowed to view
			@param filter: Query which should be altered.
			@type filter: ndb.query
			@return: altered ndb.query
		"""
		user = users.get_current_user() #Check the GAE API
		if users.is_current_user_admin():
			return( filter )
		if "user" in dir( conf["viur.mainApp"] ): #Check for our custom user-api
			user = conf["viur.mainApp"].user.getCurrentUser()
			if user and user["access"] \
				and ("%s-view" % self.modulName in user["access"] or "root" in user["access"] ) :
					return( filter )
		return( None )

	def canAdd( self ):
		"""
			Checks if the current user has the right to add a new entry
			@returns: True, if hes allowed to do so, False otherwise.
		"""
		user = utils.getCurrentUser()
		if not user:
			return( False )
		if user["access"] and "root" in user["access"]:
			return( True )
		if user and user["access"] and "%s-add" % self.modulName in user["access"]:
			return( True )
		return( False )

	def canPreview( self ):
		"""
			Checks if the current user has the right to use the preview function
			@returns: True, if hes allowed to do so, False otherwise.
		"""
		user = utils.getCurrentUser()
		if not user:
			return( False )
		if user["access"] and "root" in user["access"]:
			return( True )
		if user and  user["access"] and ("%s-add" % self.modulName in user["access"] or  "%s-edit" % self.modulName in user["access"] ):
			return( True )

	def canEdit( self, id ):
		"""
			Checks if the current user has the right to edit the given entry
			@param id: Urlsafe-key of the entry
			@type id: String
			@returns: True, if hes allowed to do so, False otherwise.
		"""
		user = utils.getCurrentUser()
		if not user:
			return( False )
		if user["access"] and "root" in user["access"]:
			return( True )
		if user and user["access"] and "%s-edit" % self.modulName in user["access"]:
			return( True )
		return( False )

	def canDelete( self, id ):
		"""
			Checks if the current user has the right to delete the given entry
			@param id: Urlsafe-key of the entry
			@type id: String
			@returns: True, if hes allowed to do so, False otherwise.
		"""
		user = utils.getCurrentUser()
		if not user:
			return( False )
		if user["access"] and "root" in user["access"]:
			return( True )
		if user and user["access"] and "%s-delete" % self.modulName in user["access"]:
			return( True )
		return( False )
		
	def onItemAdded( self, id, skel ):
		"""
			Hook. Can be overriden to hook the onItemAdded-Event
			@param id: Urlsafe-key of the entry added
			@type id: String
			@param skel: Skeleton with the data which has been added
			@type skel: Skeleton
		"""
		logging.info("Entry added: %s" % id )
		user = utils.getCurrentUser()
		if user:
			logging.info("User: %s (%s)" % (user["name"], user["id"] ) )
	
	def onItemEdited( self, id, skel ):
		"""
			Hook. Can be overriden to hook the onItemEdited-Event
			@param id: Urlsafe-key of the entry edited
			@type id: String
			@param skel: Skeleton with the data which has been edited
			@type skel: Skeleton
		"""
		logging.info("Entry changed: %s" % id )
		user = utils.getCurrentUser()
		if user:
			logging.info("User: %s (%s)" % (user["name"], user["id"] ) )
		
	def onItemViewed( self, id, skel ):
		"""
			Hook. Can be overriden to hook the onItemViewed-Event
			@param id: Urlsafe-key of the entry viewed
			@type id: String
			@param skel: Skeleton with the data which has been viewed
			@type skel: Skeleton
		"""
		pass
	
	def onItemDeleted( self, id, skel ):
		"""
			Hook. Can be overriden to hook the onItemDeleted-Event
			Note: Saving the skeleton again will undo the deletion.
			@param id: Urlsafe-key of the entry deleted
			@type id: String
			@param skel: Skeleton with the data which has been deleted
			@type skel: Skeleton
		"""
		logging.info("Entry deleted: %s" % id )
		user = utils.getCurrentUser()
		if user:
			logging.info("User: %s (%s)" % (user["name"], user["id"] ) )
	
List.admin=True
List.jinja2=True
List.ops=True