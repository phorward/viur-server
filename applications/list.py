# -*- coding: utf-8 -*-
from server.skeleton import Skeleton, skeletonByKind
from server import utils, session,  errors, conf, securitykey, request
from server import forcePost, forceSSL, exposed, internalExposed
import logging

class List( object ):
	"""
	List is a ViUR BasicApplication that is used for multiple data entities of the same kind.

	The BasicApplication must be sub-classed for individual modules and provided the kindName
	member set.

	:ivar kindName: Name of the kind of data entities that are managed by the application. \
	This information is used to bind a specific :class:`server.skeleton.Skeleton`-class to the \
	application. For more information, refer to the function :func:`~server.applications.list._resolveSkel`.
	:vartype kindName: str

	:ivar adminInfo: todo short info on how to use adminInfo.
	:vartype adminInfo: dict | callable
	"""

	kindName = None

	adminInfo = {
		"name": "BaseList",         # Module name as shown in the admin tools
		"handler": "list",          # Which handler to invoke
		"icon": "",                 # Icon for this module
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

	def _resolveSkel(self):
		"""
		Retrieve the a generally associated :class:`server.skeleton.Skeleton` that is used by
		the application.

		This is either be defined by the member variable *kindName* or by a Skeleton named like the
		application class in lower-case order.

		The function can be overridden by a general function returning the wanted Skeleton.

		:return: Returns a Skeleton instance that matches the application.
		:rtype: server.skeleton.Skeleton
		"""

		if self.kindName:
			kName = self.kindName
		else:
			kName = unicode( type(self).__name__ ).lower()

		return skeletonByKind( kName )()

	def viewSkel( self, *args, **kwargs ):
		"""
		Retrieve a new instance of a :class:`server.skeleton.Skeleton` that is used by the application
		for viewing an existing entry from the list.

		The default is a Skeleton instance returned by :func:`_resolveSkel`.

		.. seealso:: :func:`addSkel`, :func:`editSkel`, :func:`_resolveSkel`

		:return: Returns a Skeleton instance for viewing an entry.
		:rtype: server.skeleton.Skeleton
		"""
		return self._resolveSkel()

	def addSkel( self, *args, **kwargs ):
		"""
		Retrieve a new instance of a :class:`server.skeleton.Skeleton` that is used by the application
		for adding an entry to the list.

		The default is a Skeleton instance returned by :func:`_resolveSkel`.

		.. seealso:: :func:`viewSkel`, :func:`editSkel`, :func:`_resolveSkel`

		:return: Returns a Skeleton instance for adding an entry.
		:rtype: server.skeleton.Skeleton
		"""
		return self._resolveSkel()

	def editSkel( self, *args, **kwargs ):
		"""
		Retrieve a new instance of a :class:`server.skeleton.Skeleton` that is used by the application
		for editing an existing entry from the list.

		The default is a Skeleton instance returned by :func:`_resolveSkel`.

		.. seealso:: :func:`viewSkel`, :func:`editSkel`, :func:`_resolveSkel`

		:return: Returns a Skeleton instance for adding an entry.
		:rtype: server.skeleton.Skeleton
		"""
		return self._resolveSkel()

## External exposed functions

	@exposed
	@forcePost
	def preview( self, skey, *args, **kwargs ):
		"""
		Renders data for an entry, without reading from the database.
		This function allows to preview a list entry without having to save it first.

		Values a provided via *kwargs*, and must

		The function uses the viewTemplate of the application.

		:returns: The rendered preview object of the supplied data.
		"""
		if not self.canPreview( ):
			raise errors.Unauthorized()

		if not securitykey.validate( skey ):
			raise errors.PreconditionFailed()

		skel = self.viewSkel()
		# fixme: self.canPreview() is not called??

		skel.fromClient( kwargs )

		return self.render.view( skel )


	@exposed
	def view( self, *args, **kwargs ):
		"""
		Prepares and renders a single entry for viewing.

		The entry is fetched by its entity key, which either is provided via *kwargs["id"]*,
		or as the first parameter in *args*. The function runs several access control checks
		on the loaded data before it is rendered.

		.. seealso:: :func:`viewSkel`, :func:`canView`, :func:`onItemViewed`

		:returns: The rendered object of the entry.

		:raises: :exc:`server.errors.NotAcceptable`, when no *id* is provided.
		:raises: :exc:`server.errors.NotFound`, when no entry with the given *id* was found.
		:raises: :exc:`server.errors.Unauthorized`, if the current user does not have the required permissions.
		"""
		if "id" in kwargs:
			id = kwargs["id"]
		elif( len( args ) >= 1 ):
			id= args[0]
		else:
			raise errors.NotAcceptable()

		skel = self.viewSkel()

		if "canView" in dir( self ):
			if not skel.fromDB( id ):
				raise errors.NotFound()

			if not self.canView( skel ):
				raise errors.Unauthorized()

		else:
			queryObj = self.viewSkel().all().mergeExternalFilter( {"id":  id} )
			queryObj = self.listFilter( queryObj ) #Access control

			if queryObj is None:
				raise errors.Unauthorized()

			skel = queryObj.getSkel()
			if not skel:
				raise errors.NotFound()

		self.onItemViewed( skel )
		return self.render.view( skel )


	@exposed
	def list( self, *args, **kwargs ):
		"""
		Prepares and renders a list of entries.

		All supplied parameters are interpreted as filters for the elements displayed.

		Unlike other ViUR BasicApplications, the access control in this function is performed
		by calling the function :func:`listFilter`, which updates the query-filter to match only
		elements which the user is allowed to see.

		:returns: The rendered list objects for the matching entries.

		:raises: :exc:`server.errors.Unauthorized`, if the current user does not have the required permissions.
		"""
		query = self.listFilter( self.viewSkel().all().mergeExternalFilter( kwargs ) ) #Access control
		if query is None:
			raise errors.Unauthorized()

		return self.render.list( query.fetch() )

	@forceSSL
	@exposed
	def edit( self, *args, **kwargs ):
		"""
		Modify an existing entry, and render the entry, eventually with error notes on incorrect data.

		The entry is fetched by its entity key, which either is provided via *kwargs["id"]*,
		or as the first parameter in *args*. The function runs several access control checks
		on the data before it is modified.

		.. seealso:: :func:`editSkel`, :func:`onItemEdited`, :func:`canEdit`

		:returns: The rendered, edited object of the entry, eventually with error hints.

		:raises: :exc:`server.errors.NotAcceptable`, when no *id* is provided.
		:raises: :exc:`server.errors.NotFound`, when no entry with the given *id* was found.
		:raises: :exc:`server.errors.Unauthorized`, if the current user does not have the required permissions.
		:raises: :exc:`server.errors.PreconditionFailed`, if the *skey* could not be verified.
		"""

		if "skey" in kwargs:
			skey = kwargs["skey"]
		else:
			skey = ""

		if len( args ) == 1:
			id = args[0]
		elif "id" in kwargs:
			id = kwargs["id"]
		else:
			raise errors.NotAcceptable()

		skel = self.editSkel()

		if not skel.fromDB( id ):
			raise errors.NotAcceptable()

		if not self.canEdit( skel ):
			raise errors.Unauthorized()

		if (    len(kwargs) == 0 # no data supplied
				or skey == "" # no security key
				or not request.current.get().isPostRequest # failure if not using POST-method
				or not skel.fromClient(kwargs) # failure on reading into the bones
				or ("bounce" in list(kwargs.keys()) and kwargs["bounce"]=="1") # review before changing
		        ):

			# render the skeleton in the version it could as far as it could be read.
			return self.render.edit( skel )

		if not securitykey.validate( skey, acceptSessionKey=True ):
			raise errors.PreconditionFailed()

		skel.toDB() # write it!
		self.onItemEdited( skel )

		return self.render.editItemSuccess( skel )


	@forceSSL
	@exposed
	def add( self, *args, **kwargs ):
		"""
		Add a new entry, and render the entry, eventually with error notes on incorrect data.

		The function runs several access control checks on the data before it is added.

		.. seealso:: :func:`addSkel`, :func:`onItemAdded`, :func:`canAdd`

		:returns: The rendered, added object of the entry, eventually with error hints.

		:raises: :exc:`server.errors.NotFound`, when no entry with the given *id* was found.
		:raises: :exc:`server.errors.Unauthorized`, if the current user does not have the required permissions.
		:raises: :exc:`server.errors.PreconditionFailed`, if the *skey* could not be verified.
		"""

		if "skey" in kwargs:
			skey = kwargs["skey"]
		else:
			skey = ""

		if not self.canAdd():
			raise errors.Unauthorized()

		skel = self.addSkel()

		if (    len(kwargs) == 0 # no data supplied
				or skey == "" # no skey supplied
		        or not request.current.get().isPostRequest # failure if not using POST-method
		        or not skel.fromClient( kwargs ) # failure on reading into the bones
		        or ("bounce" in list(kwargs.keys()) and kwargs["bounce"]=="1") # review before adding
		        ):
			# render the skeleton in the version it could as far as it could be read.
			return self.render.add( skel )

		if not securitykey.validate( skey, acceptSessionKey=True ):
			raise errors.PreconditionFailed()

		skel.toDB()
		self.onItemAdded( skel )

		return self.render.addItemSuccess( skel )

	@forceSSL
	@forcePost
	@exposed
	def delete( self, id, skey, *args, **kwargs ):
		"""
		Delete an entry.

		The function runs several access control checks on the data before it is deleted.

		.. seealso:: :func:`editSkel`, :func:`onItemDeleted`

		:returns: The rendered, deleted object of the entry.

		:raises: :exc:`server.errors.NotFound`, when no entry with the given *id* was found.
		:raises: :exc:`server.errors.Unauthorized`, if the current user does not have the required permissions.
		:raises: :exc:`server.errors.PreconditionFailed`, if the *skey* could not be verified.
		"""

		skel = self.editSkel()
		if not skel.fromDB( id ):
			raise errors.NotFound()

		if not self.canDelete( skel ):
			raise errors.Unauthorized()

		if not securitykey.validate( skey, acceptSessionKey=True ):
			raise errors.PreconditionFailed()

		skel.delete( )
		self.onItemDeleted( skel )

		return self.render.deleteSuccess( skel )


## Default access control functions

	def listFilter( self, filter ):
		"""
		Access control function on item listing.

		This function is invoked by the :func:`list` renderer and the related Jinja2 fetching function,
		and is used to modify the provided filter parameter to match only items that the current user
		is allowed to see.

		:param filter: Query which should be altered.
		:type filter: :class:`server.db.Query`

		:returns: The altered filter, or None if access is not granted.
		:type filter: :class:`server.db.Query`
		"""
		user = utils.getCurrentUser()

		if user and ("%s-view" % self.modulName in user["access"] or "root" in user["access"] ):
			return filter

		return None


	def canAdd( self ):
		"""
		Access control function for adding permission.

		Checks if the current user has the permission to add a new entry.

		The default behavior is:
		- If no user is logged in, adding is generally refused.
		- If the user has "root" access, adding is generally allowed.
		- If the user has the modules "add" permission (module-add) enabled, adding is allowed.

		It should be overridden for a module-specific behavior.

		.. seealso:: :func:`add`

		:returns: True, if adding entries is allowed, False else.
		:rtype: bool
		"""
		user = utils.getCurrentUser()
		if not user:
			return False

		# root user is always allowed.
		if user["access"] and "root" in user["access"]:
			return True

		# user with add-permission is allowed.
		if user and user["access"] and "%s-add" % self.modulName in user["access"]:
			return True

		return False


	def canPreview( self ):
		"""
		Access control function for preview permission.

		Checks if the current user has the permission to preview an entry.
		It should be overridden for module-specific behavior.

		The default behavior is:
		- If no user is logged in, previewing is generally refused.
		- If the user has "root" access, previewing is generally allowed.
		- If the user has the modules "add" or "edit" permission (module-add, module-edit) enabled, \
		previewing is allowed.

		It should be overridden for a module-specific behavior.

		.. seealso:: :func:`preview`

		:returns: True, if previewing entries is allowed, False else.
		:rtype: bool
		"""
		user = utils.getCurrentUser()
		if not user:
			return False

		if user["access"] and "root" in user["access"]:
			return True

		if (    user and user["access"]
		        and ( "%s-add" % self.modulName in user["access"]
		                or "%s-edit" % self.modulName in user["access"]
		              )
		        ):
			return True

		return False


	def canEdit( self, skel ):
		"""
		Access control function for modification permission.

		Checks if the current user has the permission to edit an entry.

		The default behavior is:
		- If no user is logged in, editing is generally refused.
		- If the user has "root" access, editing is generally allowed.
		- If the user has the modules "edit" permission (module-edit) enabled, editing is allowed.

		It should be overridden for a module-specific behavior.

		.. seealso:: :func:`edit`

		:param skel: The Skeleton that should be edited.
		:type skel: :class:`server.skeleton.Skeleton`

		:returns: True, if editing entries is allowed, False else.
		:rtype: bool
		"""
		user = utils.getCurrentUser()
		if not user:
			return False

		if user["access"] and "root" in user["access"]:
			return True

		if user and user["access"] and "%s-edit" % self.modulName in user["access"]:
			return True

		return False


	def canDelete( self, skel ):
		"""
		Access control function for delete permission.

		Checks if the current user has the permission to edit an entry.

		The default behavior is:
		- If no user is logged in, editing is generally refused.
		- If the user has "root" access, editing is generally allowed.
		- If the user has the modules "edit" permission (module-edit) enabled, editing is allowed.

		It should be overridden for a module-specific behavior.

		:param skel: The Skeleton that should be deleted.
		:type skel: :class:`server.skeleton.Skeleton`

		.. seealso:: :func:`edit`

		:returns: True, if editing entries is allowed, False else.
		:rtype: bool
		"""
		user = utils.getCurrentUser()
		if not user:
			return( False )
		if user["access"] and "root" in user["access"]:
			return( True )
		if user and user["access"] and "%s-delete" % self.modulName in user["access"]:
			return( True )
		return( False )


## Override-able event-hooks

	def onItemAdded( self, skel ):
		"""
		Hook function that is called after adding an entry.

		It should be overridden for a module-specific behavior.
		The default is writing a log entry.

		:param skel: The Skeleton that has been added.
		:type skel: :class:`server.skeleton.Skeleton`

		.. seealso:: :func:`add`
		"""
		logging.info("Entry added: %s" % skel["id"].value )

		user = utils.getCurrentUser()
		if user:
			logging.info("User: %s (%s)" % (user["name"], user["id"] ) )


	def onItemEdited( self, skel ):
		"""
		Hook function that is called after modifying an entry.

		It should be overridden for a module-specific behavior.
		The default is writing a log entry.

		:param skel: The Skeleton that has been modified.
		:type skel: :class:`server.skeleton.Skeleton`

		.. seealso:: :func:`add`
		"""
		logging.info("Entry changed: %s" % skel["id"].value )

		user = utils.getCurrentUser()
		if user:
			logging.info("User: %s (%s)" % (user["name"], user["id"] ) )


	def onItemViewed( self, skel ):
		"""
		Hook function that is called after viewing an entry.

		It should be overridden for a module-specific behavior.
		The default is doing nothing.

		:param skel: The Skeleton that is viewed.
		:type skel: :class:`server.skeleton.Skeleton`

		.. seealso:: :func:`view`
		"""
		pass
	
	def onItemDeleted( self, skel ):
		"""
		Hook function that is called after deleting an entry.

		It should be overridden for a module-specific behavior.
		The default is writing a log entry.

		:param skel: The Skeleton that has been deleted.
		:type skel: :class:`server.skeleton.Skeleton`

		.. seealso:: :func:`delete`
		"""
		logging.info("Entry deleted: %s" % skel["id"].value )
		user = utils.getCurrentUser()
		if user:
			logging.info("User: %s (%s)" % (user["name"], user["id"] ) )

List.admin = True
List.jinja2 = True
List.vi = True
