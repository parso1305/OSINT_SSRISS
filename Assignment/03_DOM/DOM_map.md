# Homepage mapping for news , events and other essentials stuff . 
```text
NEWS
├── Container → .news-section
├── Items → .views-row
├── Image → .views-field-field-media-image img
├── Date → .news-card-date time
├── Title → .news-card-title
└── Link → .news-card-more a


RESEARCH
├── Container → .research-section
├── View → .view-research-highlights
├── Items → .views-row
├── Image → .views-field-field-highlight-image
├── Link → .views-field-field-highlight-image a
├── Date → .res-date
├── Title → .res-title
└── Body → .res-body


GALLERY
├── Container → .homepage-gallery
└── Images → [find]
```
# selector can be used 
```text
Main content -> 	        #content
Article -> 	                article.node
Main content container -> 	.node__content
News section -> 	        .news-section
News component -> 	        .homepage-news
News View -> 	            .view-homepage-news
Individual news item -> 	.views-row
Image field -> 	            .views-field-field-media-image
Events -> 	                .event-section
Research -> 	            .research-section
Government links ->     	.event-govt-links
Gallery ->              	.homepage-gallery
Footer -> 	                .site-footer

```
