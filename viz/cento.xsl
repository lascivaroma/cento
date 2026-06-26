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
         <xsl:when test="$text = '' or $replace = '' or not($replace)">
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
            <meta charset="UTF-8"/>
            <style>
               body { font-family: serif; font-size: 14px; }
               table { border-collapse: collapse; width: 100%; }
               th { text-align: left; border-bottom: 2px solid #ccc; padding: 4px 8px; }
               td { vertical-align: top; padding: 4px 8px; border-bottom: 1px solid #eee; }
               td:first-child { white-space: nowrap; }
               .seg-marker { color: #aaa; margin: 0 2px; }
               .word { display: inline-flex; flex-direction: column; align-items: center; margin: 0 2px; vertical-align: bottom; }
               .word-form { line-height: 1.4; }
               .word-meter { font-size: 0.75em; line-height: 1; color: #555; letter-spacing: 1px; white-space: nowrap; }
               .syll-long  { color: #1a1aff; }
               .syll-short { color: #cc3300; }
               .syll-elided { color: #aaa; }
               .syll-anceps { color: #888; }
               .need-check { background: #fff8e1; }
            </style>
         </head>
         <body>
            <table>
               <thead>
                  <tr>
                     <th style="width:2em;">#</th>
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
         <xsl:if test="@need_check = 'true'">
            <xsl:attribute name="class">need-check</xsl:attribute>
         </xsl:if>
         <td style="color:#999;font-size:0.85em;text-align:right;padding-right:6px;width:2em;">
            <xsl:value-of select="@n" />
         </td>
         <td>
            <xsl:apply-templates select="tei:seg" />
         </td>
         <td>
            <xsl:for-each select="tei:seg/@source">
               <span class="seg-marker">⊝</span>
               <xsl:call-template name="string-replace-all">
                  <xsl:with-param name="text" select="." />
                  <xsl:with-param name="replace" select="'urn:cts:latinLit:phi0690.'" />
                  <xsl:with-param name="by" select="''" />
               </xsl:call-template>
               <xsl:text> </xsl:text>
            </xsl:for-each>
         </td>
      </tr>
   </xsl:template>

   <xsl:template match="tei:seg">
      <span class="seg-marker">⊝</span>
      <xsl:apply-templates />
   </xsl:template>

   <xsl:template match="tei:w">
      <xsl:choose>
         <xsl:when test="starts-with(./text(), '{')"/>
         <xsl:when test="not(tei:s)">
            <!-- No syllable data: render word form only -->
            <span class="word">
               <span class="word-form"><xsl:value-of select="@form" /></span>
            </span>
            <xsl:text> </xsl:text>
         </xsl:when>
         <xsl:otherwise>
            <span class="word">
               <span class="word-form"><xsl:value-of select="@form" /></span>
               <span class="word-meter">
                  <xsl:apply-templates select="tei:s" />
               </span>
            </span>
            <xsl:text> </xsl:text>
         </xsl:otherwise>
      </xsl:choose>
   </xsl:template>

   <xsl:template match="tei:s">
      <xsl:choose>
         <xsl:when test="@met = 'long'">
            <span class="syll-long">–</span><xsl:text>&#160;</xsl:text>
         </xsl:when>
         <xsl:when test="@met = 'short'">
            <span class="syll-short">∪</span><xsl:text>&#160;</xsl:text>
         </xsl:when>
         <xsl:when test="@met = 'elided'">
            <span class="syll-elided">(</span><xsl:text>&#160;</xsl:text>
         </xsl:when>
         <xsl:when test="@met = 'anceps' or @met = 'end'">
            <span class="syll-anceps">×</span><xsl:text>&#160;</xsl:text>
         </xsl:when>
      </xsl:choose>
   </xsl:template>

</xsl:stylesheet>
