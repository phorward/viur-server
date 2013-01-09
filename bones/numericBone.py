# -*- coding: utf-8 -*-
from server.bones import baseBone

class numericBone( baseBone ):
	"""
		Holds numeric values.
		Can be used for ints and floats.
		For floats, the precision can be specified in decimal-places.
	"""
		
	type = "numeric"

	def __init__(self, precision=0, min=-100000000000, max=100000000000,   *args,  **kwargs ):
		"""
		Initializes a new NumericBone.
		@param precision: How may decimal places should be saved. Zero casts the value to int instead of float.
		@type precision: int
		@param min: Minumum accepted value (including).
		@type min: float
		@param max: Maximum accepted value (including).
		@type max: float
		"""
		baseBone.__init__( self,  *args,  **kwargs )
		self.precision = precision
		if not self.precision and "mode" in kwargs.keys() and kwargs["mode"]=="float": #Fallback for old API
			self.precision = 8
		self.min = min
		self.max = max

	def fromClient( self, value ):
		try:
			value = str( value ).replace(",", ".", 1)
		except:
			self.value = None
			return( "Invalid value entered" )
		if self.precision and ( str( value ).replace(".","",1).replace("-", "", 1).isdigit() ) and float( value )>=self.min and float( value )<=self.max:
				self.value = round( float( value ), self.precision )
				return( None )
		elif not self.precision and ( str( value ).replace("-", "", 1).isdigit() ):
				self.value = ( int( value ) )
				return( None )
		else:
			self.value = None
			return( "Invalid value entered" )
	
	def serialize( self, name ):
		if isinstance( self.value,  float ) and self.value!= self.value: # NaN
			return( {name: None } )
		else:
			return( {name:  self.value  } )
		
	def unserialize( self, name, expando ):
		if not name in expando._properties.keys():
			self.value = None
			return
		if getattr( expando, name )==None or not str(getattr( expando, name )).replace(".", "", 1).lstrip("-").isdigit():
			self.value = None
		else:
			if not self.precision:
				self.value = int( getattr( expando, name ) )
			else:
				self.value = float( getattr( expando, name ) )

	def buildDBFilter( self, name, skel, dbFilter, rawFilter ):
		if not self.precision:
			filter = dict( [ ( k, int( v ) ) for k,v in rawFilter.items() if k.startswith( name ) ] )
		else:
			filter = dict( [ ( k, float( v ) ) for k,v in rawFilter.items() if k.startswith( name ) ] )
		return( super( numericBone, self ).buildDBFilter( name, skel, dbFilter, filter ) )