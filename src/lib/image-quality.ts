export interface ImageQualityMetrics {
  meanLuminance: number
  shadowClipPercent: number
  highlightClipPercent: number
  edgeEnergy: number
}

export interface ImageQualityAssessment {
  metrics: ImageQualityMetrics
  notes: string[]
}

const round = (value:number, decimals=1) => {
  const factor=10**decimals
  return Math.round(value*factor)/factor
}

export function assessImagePixels(data:Uint8ClampedArray, width:number, height:number):ImageQualityAssessment {
  const notes:string[]=[]
  const pixels=Math.max(1,width*height)
  const gray=new Float32Array(pixels)
  let sum=0, shadows=0, highlights=0
  for(let i=0,p=0;i<data.length&&p<pixels;i+=4,p++){
    const y=(0.2126*data[i])+(0.7152*data[i+1])+(0.0722*data[i+2])
    gray[p]=y;sum+=y
    if(y<12)shadows++
    if(y>248)highlights++
  }
  let edgeSum=0,edgeCount=0
  for(let y=1;y<height;y++){
    for(let x=1;x<width;x++){
      const i=(y*width)+x
      edgeSum+=Math.abs(gray[i]-gray[i-1])+Math.abs(gray[i]-gray[i-width])
      edgeCount+=2
    }
  }
  const metrics={
    meanLuminance:round(sum/pixels),
    shadowClipPercent:round((shadows/pixels)*100),
    highlightClipPercent:round((highlights/pixels)*100),
    edgeEnergy:round(edgeCount?edgeSum/edgeCount:0,2),
  }
  if(metrics.meanLuminance<45)notes.push('Image is very dark; retake with more even light so tissue color and surface detail are visible.')
  else if(metrics.meanLuminance>225)notes.push('Image is very bright; reduce glare or exposure so pale tissue and lesions are not washed out.')
  if(metrics.shadowClipPercent>22)notes.push('Large dark areas are clipped; include more usable shadow detail.')
  if(metrics.highlightClipPercent>15)notes.push('Large bright areas are clipped; avoid direct glare or overexposure.')
  if(metrics.edgeEnergy<4.5)notes.push('Fine edge detail is limited; hold the camera steady, focus on the affected tissue, and retake closer if possible.')
  return{metrics,notes}
}

export function inspectImageElement(image:HTMLImageElement, sampleSize=160):ImageQualityAssessment|null {
  try{
    const width=Math.max(1,Math.min(sampleSize,image.naturalWidth))
    const scale=width/image.naturalWidth
    const height=Math.max(1,Math.min(sampleSize,Math.round(image.naturalHeight*scale)))
    const canvas=document.createElement('canvas')
    canvas.width=width;canvas.height=height
    const ctx=canvas.getContext('2d',{willReadFrequently:true})
    if(!ctx)return null
    ctx.drawImage(image,0,0,width,height)
    const pixels=ctx.getImageData(0,0,width,height)
    return assessImagePixels(pixels.data,width,height)
  }catch{return null}
}
