<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
   xmlns:xs="http://www.w3.org/2001/XMLSchema"
   xmlns:math="http://www.w3.org/2005/xpath-functions/math"
   xmlns:tei="http://www.tei-c.org/ns/1.0"
   xmlns="http://www.tei-c.org/ns/1.0"
   exclude-result-prefixes="xs math tei"
   version="1.0">
   <xsl:template name="string-replace-all">
    <xsl:param name="text" />
    <xsl:param name="replace" />
    <xsl:param name="by" />
    <xsl:choose>
        <xsl:when test="$text = '' or $replace = ''or not($replace)" >
            <!-- Prevent this routine from hanging -->
            <xsl:value-of select="$text" />
        </xsl:when>
        <xsl:when test="contains($text, $replace)">
            <xsl:value-of select="substring-before($text,$replace)" />
            <xsl:value-of select="$by" />
            <xsl:call-template name="string-replace-all">
                <xsl:with-param name="text" select="substring-after($text,$replace)" />
                <xsl:with-param name="replace" select="$replace" />
                <xsl:with-param name="by" select="$by" />
            </xsl:call-template>
        </xsl:when>
        <xsl:otherwise>
            <xsl:value-of select="$text" />
        </xsl:otherwise>
    </xsl:choose>
</xsl:template>


   <xsl:template match="/tei:TEI/tei:text/tei:body">
      <html>
         <head>
         </head>
         <body>
            <table>
               <thead>
                  <tr>
                     <th>Line</th>
                     <th>Sources</th>
                  </tr>
               </thead>
               <tbody>
                  <xsl:apply-templates />
               </tbody>
            </table>
         </body>
      </html>
   </xsl:template>

   <xsl:template match="tei:l">
      <tr>
         <td>
            <xsl:apply-templates select="tei:seg" />
         </td>
         <td>
            <xsl:for-each select="tei:seg/@source">
             <xsl:call-template name="string-replace-all">
                 <xsl:with-param name="text" select="." />
                 <xsl:with-param name="replace" select="'urn:cts:latinLit:phi0690.'" />
                 <xsl:with-param name="by" select="''" />
             </xsl:call-template>
            </xsl:for-each>
         </td>
      </tr>
   </xsl:template>

   <xsl:template match="tei:seg">
      ⊝ <xsl:apply-templates />
   </xsl:template>
   <xsl:template match="tei:w">
      <xsl:choose>
         <xsl:when test="starts-with(./text(), '{')"/>
         <xsl:otherwise>
            <xsl:apply-templates />
         </xsl:otherwise>
      </xsl:choose>
   </xsl:template>
   
</xsl:stylesheet>