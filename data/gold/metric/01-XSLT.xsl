<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
   xmlns:xs="http://www.w3.org/2001/XMLSchema"
   xmlns:math="http://www.w3.org/2005/xpath-functions/math"
   xmlns:xhtml="http://www.w3.org/1999/xhtml"
   xmlns="http://www.tei-c.org/ns/1.0"
                xmlns:f="https://foo.bar"
   exclude-result-prefixes="xs math xhtml"
   version="1.0">

   <xsl:template match="xhtml:html">
   	<xsl:apply-templates select="//xhtml:div[contains(@class, 'poem')]"/>
   </xsl:template>

   <xsl:template match="xhtml:div[contains(@class, 'poem')]">
      <TEI>
      	<text>
      		<body>
      			<xsl:apply-templates select="xhtml:div" />
      		</body>
      	</text>
      </TEI>
   </xsl:template>

   <xsl:template match="xhtml:div[contains(@class, 'line')]">
   	 <l>
   	 	<xsl:apply-templates />
   	 </l><xsl:text>
   	</xsl:text>
   </xsl:template>

   <xsl:template match="xhtml:span[@class='word']">
   	<w>
        <xsl:attribute name="form"><xsl:apply-templates select="./xhtml:span/text()"/></xsl:attribute>
   		<xsl:apply-templates/>
   	</w>
   </xsl:template>

   <xsl:template match="xhtml:span[contains(@class, 'syll')]">
      <s>
         <xsl:attribute name="met">
            <xsl:choose>
               <xsl:when test="contains(@class, 'end')">end</xsl:when>
               <xsl:when test="contains(@class, 'long')">long</xsl:when>
               <xsl:when test="contains(@class, 'elided')">elided</xsl:when>
               <xsl:otherwise>short</xsl:otherwise>
            </xsl:choose>
         </xsl:attribute>
          <xsl:if test="contains(@class, 'caesura')"><caesura /></xsl:if>
         <xsl:apply-templates/>
      </s>
   </xsl:template>

    <xsl:template match="text()">
        <xsl:value-of select="f:normalize(.)" />
    </xsl:template>
   
</xsl:stylesheet>